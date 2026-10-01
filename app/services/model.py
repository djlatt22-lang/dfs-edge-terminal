from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Iterable

from .math_utils import devig_two_way, norm_cdf, norm_ppf


# Approximate one-game / one-match standard deviations. They are fallbacks, not claims of universal truth.
# Users should calibrate these against their own historical exports for production use.
MARKET_SIGMA = {
    # NFL / CFB
    "player_pass_yds": 55.0,
    "player_pass_attempts": 5.5,
    "player_pass_completions": 5.0,
    "player_pass_tds": 1.05,
    "player_rush_yds": 28.0,
    "player_rush_attempts": 4.2,
    "player_reception_yds": 25.0,
    "player_receptions": 2.1,
    "player_tackles_assists": 2.7,
    "player_solo_tackles": 2.0,
    "player_fantasy_points": 6.0,
    # NBA / WNBA / NCAAB
    "player_points": 7.0,
    "player_rebounds": 3.2,
    "player_assists": 2.6,
    "player_threes": 1.6,
    "player_points_rebounds_assists": 10.0,
    "player_points_assists": 8.5,
    "player_points_rebounds": 8.8,
    "player_rebounds_assists": 5.0,
    "player_blocks_steals": 1.7,
    # MLB
    "pitcher_strikeouts": 2.2,
    "pitcher_outs": 3.7,
    "pitcher_hits_allowed": 2.1,
    "pitcher_walks": 1.3,
    "pitcher_earned_runs": 1.8,
    "batter_hits": 0.8,
    "batter_total_bases": 1.8,
    "batter_runs_scored": 0.65,
    "batter_rbis": 0.8,
    "batter_walks": 0.55,
    "batter_strikeouts": 0.8,
    "batter_fantasy_score": 4.6,
    # NHL
    "player_shots_on_goal": 1.45,
    "player_points": 0.75,
    "player_assists": 0.65,
    "player_goals": 0.48,
    "player_blocked_shots": 1.25,
    "player_total_saves": 5.8,
    # Soccer
    "player_shots_on_target": 1.05,
}

SPORT_CV = {
    "American Football": 0.23,
    "Basketball": 0.30,
    "Baseball": 0.45,
    "Ice Hockey": 0.45,
    "Soccer": 0.55,
    "Tennis": 0.28,
    "Esports": 0.25,
}

SHARP_WEIGHTS = {
    "pinnacle": 1.65,
    "circa": 1.55,
    "fanduel": 1.15,
    "draftkings": 1.12,
    "caesars": 1.10,
    "betmgm": 1.05,
    "betrivers": 1.00,
    "espnbet": 0.98,
}

DFS_BOOKS = {"prizepicks", "underdog", "dabble_us_dfs", "pick6"}


def sigma_for_market(market_key: str, line: float, sport_group: str | None = None) -> float:
    if market_key in MARKET_SIGMA:
        return MARKET_SIGMA[market_key]
    cv = SPORT_CV.get(sport_group or "", 0.32)
    # Keep sigma usable for low-count stats and large yardage stats.
    return max(0.75, abs(float(line)) * cv)


@dataclass(slots=True)
class BookPair:
    bookmaker: str
    point: float
    over_price: float
    under_price: float
    updated: str | None = None


@dataclass(slots=True)
class ConsensusProjection:
    projection: float
    sigma: float
    over_probability_at_dfs_line: float
    under_probability_at_dfs_line: float
    source_count: int
    consensus_line: float
    line_spread: float
    confidence: float
    notes: list[str]


def infer_projection(
    *,
    dfs_line: float,
    market_key: str,
    sport_group: str | None,
    pairs: Iterable[BookPair],
) -> ConsensusProjection | None:
    pairs = list(pairs)
    if not pairs:
        return None

    sigma = sigma_for_market(market_key, dfs_line, sport_group)
    inferred: list[tuple[float, float, float]] = []  # mu, point, weight
    notes: list[str] = []

    for pair in pairs:
        fair = devig_two_way(pair.over_price, pair.under_price)
        if fair is None:
            continue
        p_over, _ = fair
        mu = float(pair.point) + sigma * norm_ppf(p_over)
        weight = SHARP_WEIGHTS.get(pair.bookmaker, 0.9)
        inferred.append((mu, float(pair.point), weight))

    if not inferred:
        return None

    total_weight = sum(x[2] for x in inferred)
    projection = sum(mu * w for mu, _, w in inferred) / total_weight
    consensus_line = sum(point * w for _, point, w in inferred) / total_weight
    points = [p for _, p, _ in inferred]
    line_spread = (max(points) - min(points)) if len(points) > 1 else 0.0

    p_over_dfs = norm_cdf((projection - dfs_line) / sigma)
    p_under_dfs = 1 - p_over_dfs

    # Confidence rewards independent market sources and agreement, but avoids implying certainty.
    source_score = min(1.0, len(inferred) / 6)
    disagreement = min(1.0, line_spread / max(sigma, 1e-9))
    edge_z = abs(projection - dfs_line) / max(sigma, 1e-9)
    separation = min(1.0, edge_z / 0.8)
    confidence = 42 + 24 * source_score + 16 * (1 - disagreement) + 14 * separation
    confidence = round(min(96.0, max(35.0, confidence)), 1)

    if len(inferred) < 3:
        notes.append("Thin sportsbook consensus")
    if line_spread > sigma * 0.45:
        notes.append("Book lines are dispersed")
    if abs(projection - dfs_line) < sigma * 0.08:
        notes.append("Small modeled separation")

    return ConsensusProjection(
        projection=round(projection, 3),
        sigma=round(sigma, 3),
        over_probability_at_dfs_line=round(p_over_dfs, 4),
        under_probability_at_dfs_line=round(p_under_dfs, 4),
        source_count=len(inferred),
        consensus_line=round(consensus_line, 3),
        line_spread=round(line_spread, 3),
        confidence=confidence,
        notes=notes,
    )


def grade_from_probability(prob: float, confidence: float) -> str:
    # Labels describe model strength, not guaranteed outcomes.
    effective = prob * (0.72 + 0.28 * (confidence / 100))
    if effective >= 0.65:
        return "A+"
    if effective >= 0.61:
        return "A"
    if effective >= 0.575:
        return "B+"
    if effective >= 0.545:
        return "B"
    return "C"
