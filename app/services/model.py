from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Iterable

from .math_utils import devig_two_way, norm_cdf, norm_ppf


# Approximate one-game / one-match standard deviations. These are conservative
# fallbacks used when we do not yet have a sport/stat-specific historical
# calibration. Live sportsbook prices still determine the center of the model.
MARKET_SIGMA = {
    # NFL / CFB aliases across supported data feeds
    "player_pass_yds": 55.0,
    "passing_yards": 55.0,
    "player_pass_attempts": 5.5,
    "passing_attempts": 5.5,
    "player_pass_completions": 5.0,
    "passing_completions": 5.0,
    "player_pass_tds": 1.05,
    "passing_tds": 1.05,
    "player_rush_yds": 28.0,
    "rushing_yards": 28.0,
    "player_rush_attempts": 4.2,
    "rushing_attempts": 4.2,
    "player_reception_yds": 25.0,
    "receiving_yards": 25.0,
    "player_receptions": 2.1,
    "receptions": 2.1,
    "player_tackles_assists": 2.7,
    "tackles_assists": 2.7,
    "player_solo_tackles": 2.0,
    "solo_tackles": 2.0,
    "player_fantasy_points": 6.0,
    "fantasy_points": 6.0,
    # NBA / WNBA / NCAAB
    "player_points": 7.0,
    "points": 7.0,
    "player_rebounds": 3.2,
    "rebounds": 3.2,
    "player_assists": 2.6,
    "assists": 2.6,
    "player_threes": 1.6,
    "three_pointers": 1.6,
    "player_points_rebounds_assists": 10.0,
    "points_rebounds_assists": 10.0,
    "player_points_assists": 8.5,
    "points_assists": 8.5,
    "player_points_rebounds": 8.8,
    "points_rebounds": 8.8,
    "player_rebounds_assists": 5.0,
    "rebounds_assists": 5.0,
    "player_blocks_steals": 1.7,
    "blocks_steals": 1.7,
    # MLB
    "pitcher_strikeouts": 2.2,
    "pitcher_outs": 3.7,
    "pitcher_hits_allowed": 2.1,
    "pitcher_walks": 1.3,
    "pitcher_earned_runs": 1.8,
    "pitcher_pitches": 13.0,
    "batter_hits": 0.8,
    "batter_total_bases": 1.8,
    "batter_runs_scored": 0.65,
    "batter_rbis": 0.8,
    "batter_walks": 0.55,
    "batter_strikeouts": 0.8,
    "batter_fantasy_score": 4.6,
    # NHL
    "player_shots_on_goal": 1.45,
    "shots_on_goal": 1.45,
    "player_points": 0.75,
    "player_goals": 0.48,
    "goals": 0.48,
    "player_blocked_shots": 1.25,
    "blocked_shots": 1.25,
    "player_total_saves": 5.8,
    "saves": 5.8,
    # Soccer
    "player_shots_on_target": 1.05,
    "shots_on_target": 1.05,
    # Esports / CS2 common aliases
    "kills_map_1": 4.8,
    "kills_maps_1_2": 6.8,
    "kills_maps_1_2_3": 8.0,
    "headshots_map_1": 3.2,
    "headshots_maps_1_2": 4.6,
    "headshots_maps_1_2_3": 5.6,
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
    "bovada": 0.92,
}

# Union of DFS keys exposed by supported feeds. The same product can have a
# different feed key (Dabble is the main example), so matching is normalized
# in the data client.
DFS_BOOKS = {
    "prizepicks",
    "underdog",
    "dabble",
    "dabble_us_dfs",
    "pick6",
    "sleeper",
    "parlayplay",
}


def sigma_for_market(market_key: str, line: float, sport_group: str | None = None) -> float:
    key = (market_key or "").lower()
    # Alternate markets use the same underlying stat distribution.
    if key.endswith("_alternate"):
        key = key[: -len("_alternate")]
    if key in MARKET_SIGMA:
        return MARKET_SIGMA[key]
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


def _freshness_weight(updated: str | None) -> float:
    """Softly down-weight stale quotes instead of treating them as equally live."""
    if not updated:
        return 0.9
    try:
        ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        age_min = max(0.0, (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 60.0)
    except Exception:
        return 0.9
    if age_min <= 5:
        return 1.0
    # 30 minute half-life after the first five minutes, bounded so a stale
    # quote can inform the center but cannot dominate it.
    return max(0.25, 0.5 ** ((age_min - 5.0) / 30.0))


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
    counts = Counter(p.bookmaker for p in pairs)
    inferred: list[tuple[float, float, float, str]] = []  # mu, point, weight, book
    notes: list[str] = []

    for pair in pairs:
        fair = devig_two_way(pair.over_price, pair.under_price)
        if fair is None:
            continue
        p_over, _ = fair
        mu = float(pair.point) + sigma * norm_ppf(p_over)
        # Do not let a single book's alternate-line ladder count like several
        # independent books. Its total influence is normalized across its rungs.
        base_weight = SHARP_WEIGHTS.get(pair.bookmaker, 0.9)
        weight = base_weight * _freshness_weight(pair.updated) / max(1, counts[pair.bookmaker])
        inferred.append((mu, float(pair.point), weight, pair.bookmaker))

    if not inferred:
        return None

    # Robustify against one bad feed/price. Implied means that are far from the
    # cross-market median are retained at reduced influence rather than dropped.
    mu_med = median(x[0] for x in inferred)
    robust: list[tuple[float, float, float, str]] = []
    for mu, point, weight, book in inferred:
        distance = abs(mu - mu_med) / max(sigma, 1e-9)
        if distance > 1.25:
            weight *= 0.2
        elif distance > 0.75:
            weight *= 0.55
        robust.append((mu, point, weight, book))

    total_weight = sum(x[2] for x in robust)
    if total_weight <= 0:
        return None
    projection = sum(mu * w for mu, _, w, _ in robust) / total_weight

    # For the displayed market center, take one quoted line per bookmaker: the
    # line nearest the DFS threshold. This avoids alternate ladders distorting it.
    nearest_by_book: dict[str, tuple[float, float]] = {}
    for _mu, point, _weight, book in robust:
        current = nearest_by_book.get(book)
        dist = abs(point - dfs_line)
        if current is None or dist < current[1]:
            nearest_by_book[book] = (point, dist)
    consensus_line = median(v[0] for v in nearest_by_book.values())

    book_means: dict[str, list[float]] = {}
    for mu, _point, _weight, book in robust:
        book_means.setdefault(book, []).append(mu)
    centers = [sum(vals) / len(vals) for vals in book_means.values()]
    model_spread = (max(centers) - min(centers)) if len(centers) > 1 else 0.0
    source_count = len(book_means)

    p_over_dfs = norm_cdf((projection - dfs_line) / sigma)
    p_under_dfs = 1 - p_over_dfs

    # Confidence rewards truly independent books, freshness/consistency and
    # separation, while explicitly avoiding certainty language.
    source_score = min(1.0, source_count / 6)
    disagreement = min(1.0, model_spread / max(sigma, 1e-9))
    edge_z = abs(projection - dfs_line) / max(sigma, 1e-9)
    separation = min(1.0, edge_z / 0.8)
    confidence = 40 + 25 * source_score + 17 * (1 - disagreement) + 13 * separation
    confidence = round(min(94.0, max(32.0, confidence)), 1)

    if source_count < 3:
        notes.append("Thin sportsbook consensus")
    if model_spread > sigma * 0.45:
        notes.append("Sportsbook implied means disagree")
    if abs(projection - dfs_line) < sigma * 0.08:
        notes.append("Small modeled separation")
    if any(_freshness_weight(p.updated) < 0.5 for p in pairs):
        notes.append("Some comparison prices are stale and down-weighted")

    return ConsensusProjection(
        projection=round(projection, 3),
        sigma=round(sigma, 3),
        over_probability_at_dfs_line=round(p_over_dfs, 4),
        under_probability_at_dfs_line=round(p_under_dfs, 4),
        source_count=source_count,
        consensus_line=round(float(consensus_line), 3),
        line_spread=round(model_spread, 3),
        confidence=confidence,
        notes=notes,
    )


def grade_from_probability(prob: float, confidence: float, source_count: int | None = None) -> str:
    """Model-strength label. Source gates prevent thin markets getting A/A+."""
    effective = prob * (0.72 + 0.28 * (confidence / 100))
    if effective >= 0.65 and confidence >= 76 and (source_count is None or source_count >= 4):
        return "A+"
    if effective >= 0.61 and confidence >= 68 and (source_count is None or source_count >= 3):
        return "A"
    if effective >= 0.575 and (source_count is None or source_count >= 2):
        return "B+"
    if effective >= 0.545:
        return "B"
    return "C"
