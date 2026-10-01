from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict
from typing import Any

import httpx

from .model import BookPair, DFS_BOOKS, grade_from_probability, infer_projection

BASE = "https://api.the-odds-api.com/v4"

PROVIDER_LABELS = {
    "prizepicks": "PrizePicks",
    "underdog": "Underdog",
    "dabble_us_dfs": "Dabble",
    "pick6": "DraftKings Pick6",
}

# Avoid non-player featured markets. Everything else discovered from a DFS book is treated dynamically.
NON_PLAYER_MARKETS = {
    "h2h", "spreads", "totals", "outrights", "team_totals", "alternate_spreads",
    "alternate_totals", "alternate_team_totals", "draw_no_bet", "btts", "h2h_3_way",
}

_CACHE: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str):
    ttl = int(os.getenv("DFS_CACHE_TTL_SECONDS", "90"))
    item = _CACHE.get(key)
    if item and (time.time() - item[0]) < ttl:
        return item[1]
    return None


def _cache_set(key: str, value: Any):
    _CACHE[key] = (time.time(), value)


class OddsApiError(RuntimeError):
    pass


class OddsApiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")
        self.max_events = int(os.getenv("DFS_MAX_EVENTS_PER_SPORT", "12"))
        self.sem = asyncio.Semaphore(int(os.getenv("DFS_REQUEST_CONCURRENCY", "5")))
        self.client = httpx.AsyncClient(timeout=24.0, headers={"User-Agent": "DFS-Edge-Terminal/1.0"})

    async def close(self):
        await self.client.aclose()

    def configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, path: str, params: dict[str, Any] | None = None):
        if not self.api_key:
            raise OddsApiError("ODDS_API_KEY is not configured")
        params = dict(params or {})
        params["apiKey"] = self.api_key
        async with self.sem:
            res = await self.client.get(f"{BASE}{path}", params=params)
        if res.status_code >= 400:
            detail = res.text[:400]
            raise OddsApiError(f"Odds API {res.status_code}: {detail}")
        return res.json()

    async def sports(self, all_sports: bool = False):
        key = f"sports:{all_sports}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        data = await self._get("/sports", {"all": str(all_sports).lower()})
        _cache_set(key, data)
        return data

    async def events(self, sport_key: str):
        key = f"events:{sport_key}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        data = await self._get(f"/sports/{sport_key}/events", {"dateFormat": "iso"})
        data = data[: self.max_events]
        _cache_set(key, data)
        return data

    async def event_markets(self, sport_key: str, event_id: str):
        key = f"markets:{sport_key}:{event_id}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        data = await self._get(
            f"/sports/{sport_key}/events/{event_id}/markets",
            {"regions": "us_dfs,us,us2", "dateFormat": "iso"},
        )
        _cache_set(key, data)
        return data

    async def event_odds(self, sport_key: str, event_id: str, markets: list[str]):
        if not markets:
            return None
        all_bookmakers: dict[str, dict] = {}
        event_shell: dict[str, Any] | None = None

        for i in range(0, len(markets), 10):
            chunk = markets[i:i + 10]
            data = await self._get(
                f"/sports/{sport_key}/events/{event_id}/odds",
                {
                    "regions": "us_dfs,us,us2",
                    "markets": ",".join(chunk),
                    "oddsFormat": "american",
                    "dateFormat": "iso",
                    "includeMultipliers": "true",
                },
            )
            if not data:
                continue
            if event_shell is None:
                event_shell = {k: data.get(k) for k in ["id", "sport_key", "sport_title", "commence_time", "home_team", "away_team"]}
            for book in data.get("bookmakers", []):
                bkey = book.get("key")
                if not bkey:
                    continue
                slot = all_bookmakers.setdefault(bkey, {"key": bkey, "title": book.get("title"), "last_update": book.get("last_update"), "markets": []})
                slot["markets"].extend(book.get("markets", []))

        if event_shell is None:
            return None
        event_shell["bookmakers"] = list(all_bookmakers.values())
        return event_shell

    @staticmethod
    def _dfs_market_keys(markets_payload: dict[str, Any]) -> list[str]:
        keys = set()
        for book in markets_payload.get("bookmakers", []):
            if book.get("key") in DFS_BOOKS:
                for market in book.get("markets", []):
                    key = market.get("key")
                    if key and key not in NON_PLAYER_MARKETS:
                        keys.add(key)
        return sorted(keys)

    async def board(self, sport_key: str, provider: str = "all"):
        events = await self.events(sport_key)
        if not events:
            return {"sport_key": sport_key, "rows": [], "events_scanned": 0, "warnings": []}

        warnings: list[str] = []

        async def hydrate(evt: dict[str, Any]):
            try:
                markets_meta = await self.event_markets(sport_key, evt["id"])
                keys = self._dfs_market_keys(markets_meta)
                if not keys:
                    return None
                return await self.event_odds(sport_key, evt["id"], keys)
            except Exception as exc:  # keep one event from killing the board
                warnings.append(f"{evt.get('away_team')} @ {evt.get('home_team')}: {exc}")
                return None

        hydrated = await asyncio.gather(*(hydrate(evt) for evt in events))
        rows = []
        for event in hydrated:
            if event:
                rows.extend(self._normalize_event(event, provider=provider))

        rows.sort(key=lambda r: (r["recommended_probability"], r["confidence"]), reverse=True)
        return {
            "sport_key": sport_key,
            "rows": rows,
            "events_scanned": len(events),
            "warnings": warnings[:10],
        }

    @staticmethod
    def _outcome_identity(outcome: dict[str, Any]) -> str:
        # Most props use description for player and name for Over/Under. Fallback to name.
        return (outcome.get("description") or outcome.get("name") or "").strip()

    def _normalize_event(self, event: dict[str, Any], provider: str = "all") -> list[dict[str, Any]]:
        books = event.get("bookmakers", [])
        dfs_books = [b for b in books if b.get("key") in DFS_BOOKS and (provider == "all" or b.get("key") == provider)]
        sportsbook_books = [b for b in books if b.get("key") not in DFS_BOOKS]

        # Index sportsbook over/under pairs by (market, player, point)
        pairs_index: dict[tuple[str, str], list[BookPair]] = defaultdict(list)
        evidence_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for book in sportsbook_books:
            for market in book.get("markets", []):
                mkey = market.get("key", "")
                grouped: dict[tuple[str, float], dict[str, Any]] = defaultdict(dict)
                for out in market.get("outcomes", []):
                    identity = self._outcome_identity(out)
                    point = out.get("point")
                    side = (out.get("name") or "").lower()
                    if not identity or point is None or side not in {"over", "under"}:
                        continue
                    grouped[(identity.lower(), float(point))][side] = out
                for (identity, point), sides in grouped.items():
                    if "over" in sides and "under" in sides:
                        pair = BookPair(
                            bookmaker=book.get("key", "unknown"),
                            point=point,
                            over_price=sides["over"].get("price"),
                            under_price=sides["under"].get("price"),
                            updated=book.get("last_update"),
                        )
                        pairs_index[(mkey, identity)].append(pair)
                        evidence_index[(mkey, identity)].append({
                            "book": book.get("title") or book.get("key"),
                            "book_key": book.get("key"),
                            "line": point,
                            "over": sides["over"].get("price"),
                            "under": sides["under"].get("price"),
                            "updated": book.get("last_update"),
                        })

        rows: list[dict[str, Any]] = []
        for book in dfs_books:
            for market in book.get("markets", []):
                mkey = market.get("key", "")
                for out in market.get("outcomes", []):
                    identity = self._outcome_identity(out)
                    point = out.get("point")
                    side_name = (out.get("name") or "").lower()
                    if not identity or point is None or side_name not in {"over", "under", "more", "less"}:
                        continue

                    # DFS feeds can emit both sides. Create one row per line/player/provider, deduplicated later.
                    pairs = pairs_index.get((mkey, identity.lower()), [])
                    projection = infer_projection(
                        dfs_line=float(point),
                        market_key=mkey,
                        sport_group=event.get("sport_title"),
                        pairs=pairs,
                    )
                    if not projection:
                        continue

                    over_prob = projection.over_probability_at_dfs_line
                    under_prob = projection.under_probability_at_dfs_line
                    rec_side = "MORE" if over_prob >= under_prob else "LESS"
                    rec_prob = max(over_prob, under_prob)
                    edge = projection.projection - float(point)
                    standardized_edge = edge / max(projection.sigma, 1e-9)
                    grade = grade_from_probability(rec_prob, projection.confidence)

                    rows.append({
                        "id": f"{event.get('id')}:{book.get('key')}:{mkey}:{identity}:{point}",
                        "provider": PROVIDER_LABELS.get(book.get("key"), book.get("title") or book.get("key")),
                        "provider_key": book.get("key"),
                        "sport": event.get("sport_title"),
                        "sport_key": event.get("sport_key"),
                        "player": identity,
                        "market": mkey,
                        "market_label": mkey.replace("_", " ").title(),
                        "line": float(point),
                        "projection": projection.projection,
                        "edge": round(edge, 3),
                        "edge_pct": round((edge / max(abs(float(point)), 1.0)) * 100, 2),
                        "z_edge": round(standardized_edge, 3),
                        "over_probability": round(over_prob * 100, 1),
                        "under_probability": round(under_prob * 100, 1),
                        "recommended_side": rec_side,
                        "recommended_probability": round(rec_prob * 100, 1),
                        "confidence": projection.confidence,
                        "grade": grade,
                        "source_count": projection.source_count,
                        "consensus_line": projection.consensus_line,
                        "line_spread": projection.line_spread,
                        "sigma": projection.sigma,
                        "multiplier": out.get("multiplier"),
                        "matchup": f"{event.get('away_team')} @ {event.get('home_team')}",
                        "away_team": event.get("away_team"),
                        "home_team": event.get("home_team"),
                        "commence_time": event.get("commence_time"),
                        "notes": projection.notes,
                        "books": evidence_index.get((mkey, identity.lower()), []),
                        "method": "de-vigged sportsbook consensus → implied distribution",
                    })

        # Dedupe duplicate More/Less representations from DFS source.
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            unique[row["id"]] = row
        return list(unique.values())
