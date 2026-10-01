from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from .math_utils import devig_two_way, norm_cdf, norm_ppf


# One-game / one-match standard-deviation priors. These are intentionally conservative
# fallbacks for converting fair market probabilities into implied stat means. Production
# calibration should replace them with historical residual distributions by sport/market.
MARKET_SIGMA = {
    # NFL / CFB
    "player_pass_yds": 55.0,
    "player_pass_attempts": 5.5,
    "player_pass_completions": 5.0,
    "player_pass_tds": 1.05,
    "player_pass_interceptions": 0.85,
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
    "player_turnovers": 1.7,
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
    "player_goals": 0.48,
    "player_blocked_shots": 1.25,
    "player_total_saves": 5.8,
    # Soccer
    "player_shots": 1.65,
    "player_shots_on_target": 1.05,
    "player_tackles": 1.7,
    # Tennis
    "player_aces": 4.0,
    "player_double_faults": 2.0,
    "player_games_won": 3.8,
    # Common esports count-style markets
    "player_kills": 5.0,
    "player_assists": 6.0,
    "player_headshots": 5.0,
    "player_map_kills": 4.0,
}

SPORT_CV = {
    "American Football": 0.23,
    "Basketball": 0.30,
    "Baseball": 0.45,
    "Ice Hockey": 0.45,
    "Soccer": 0.55,
    "Tennis": 0.28,
    "Esports": 0.25,
    "Other": 0.32,
}

SHARP_WEIGHTS = {
    "pinnacle": 1.70,
    "circa": 1.60,
    "fanduel": 1.15,
    "draftkings": 1.12,
    "caesars": 1.10,
    "betmgm": 1.05,
    "betrivers": 1.00,
    "espnbet": 0.98,
}

DFS_BOOKS = {"prizepicks", "underdog", "dabble_us_dfs", "pick6"}


def sport_group_from_key(sport_key: str | None, title: str | None = None) -> str:
    key = (sport_key or "").lower()
    if key.startswith("americanfootball_"):
        return "American Football"
    if key.startswith("basketball_"):
        return "Basketball"
    if key.startswith("baseball_"):
        return "Baseball"
    if key.startswith("icehockey_"):
        return "Ice Hockey"
    if key.startswith("soccer_"):
        return "Soccer"
    if key.startswith("tennis_"):
        return "Tennis"
    if key.startswith("esports_") or "esport" in key:
        return "Esports"
    t = (title or "").lower()
    if any(x in t for x in ("nfl", "ncaa football", "football")):
        return "American Football"
    if any(x in t for x in ("nba", "wnba", "basketball")):
        return "Basketball"
    if any(x in t for x in ("mlb", "baseball")):
        return "Baseball"
    if any(x in t for x in ("nhl", "hockey")):
        return "Ice Hockey"
    if "soccer" in t:
        return "Soccer"
    if "tennis" in t:
        return "Tennis"
    if "esport" in t:
        return "Esports"
    return "Other"


def sigma_for_market(market_key: str, line: float, sport_group: str | None = None) -> float:
    if market_key in MARKET_SIGMA:
        return MARKET_SIGMA[market_key]
    cv = SPORT_CV.get(sport_group or "Other", SPORT_CV["Other"])
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
    outliers_removed: int = 0


def _robust_filter(values: list[tuple[float, float, float, BookPair]], sigma: float):
    """Remove only extreme implied-mean outliers when the market has enough sources."""
    if len(values) < 4:
        return values, 0
    med = median(v[0] for v in values)
    deviations = [abs(v[0] - med) for v in values]
    mad = median(deviations)
    threshold = max(0.65 * sigma, 3.0 * mad if mad > 0 else 0.0)
    kept = [v for v in values if abs(v[0] - med) <= threshold]
    if len(kept) < 2:
        return values, 0
    return kept, len(values) - len(kept)


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
    inferred: list[tuple[float, float, float, BookPair]] = []
    notes: list[str] = []

    for pair in pairs:
        fair = devig_two_way(pair.over_price, pair.under_price)
        if fair is None:
            continue
        p_over, _ = fair
        # Protect the inverse-CDF transform from pathological 0/1 inputs.
        p_over = min(0.995, max(0.005, p_over))
        mu = float(pair.point) + sigma * norm_ppf(p_over)
        weight = SHARP_WEIGHTS.get(pair.bookmaker, 0.90)
        inferred.append((mu, float(pair.point), weight, pair))

    if not inferred:
        return None

    inferred, removed = _robust_filter(inferred, sigma)
    if removed:
        notes.append(f"Removed {removed} extreme sportsbook outlier{'s' if removed != 1 else ''}")

    total_weight = sum(x[2] for x in inferred)
    projection = sum(mu * w for mu, _, w, _ in inferred) / total_weight
    consensus_line = sum(point * w for _, point, w, _ in inferred) / total_weight
    points = [p for _, p, _, _ in inferred]
    line_spread = (max(points) - min(points)) if len(points) > 1 else 0.0

    p_over_dfs = norm_cdf((projection - dfs_line) / sigma)
    p_under_dfs = 1 - p_over_dfs

    source_score = min(1.0, len(inferred) / 6)
    disagreement = min(1.0, line_spread / max(sigma, 1e-9))
    edge_z = abs(projection - dfs_line) / max(sigma, 1e-9)
    separation = min(1.0, edge_z / 0.80)

    confidence = 40 + 28 * source_score + 16 * (1 - disagreement) + 12 * separation
    if len(inferred) == 1:
        confidence = min(confidence, 52)
    elif len(inferred) == 2:
        confidence = min(confidence, 68)
    elif len(inferred) == 3:
        confidence = min(confidence, 80)
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
        outliers_removed=removed,
    )


def grade_from_probability(prob: float, confidence: float) -> str:
    # Labels describe model strength, not guaranteed outcomes.
    effective = prob * (0.70 + 0.30 * (confidence / 100))
    if confidence < 55:
        return "C"
    if effective >= 0.66 and confidence >= 78:
        return "A+"
    if effective >= 0.615 and confidence >= 70:
        return "A"
    if effective >= 0.58 and confidence >= 62:
        return "B+"
    if effective >= 0.545:
        return "B"
    return "C"
