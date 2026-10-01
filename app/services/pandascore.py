from __future__ import annotations

import os
from typing import Any

import httpx

BASE = "https://api.pandascore.co"

GAME_PATHS = {
    "cs2": "csgo",
    "csgo": "csgo",
    "lol": "lol",
    "league-of-legends": "lol",
    "dota2": "dota2",
    "dota-2": "dota2",
    "valorant": "valorant",
}

# PandaScore covers more titles at the fixtures level. These are common slugs users can try.
FIXTURE_GAMES = [
    "csgo", "lol", "dota2", "valorant", "codmw", "ow", "r6siege",
    "rl", "fifa", "pubg", "fortnite", "kog", "starcraft-2", "wild-rift",
]


class PandaScoreClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("PANDASCORE_TOKEN", "")
        self.client = httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "DFS-Edge-Terminal/1.0"})

    async def close(self):
        await self.client.aclose()

    def configured(self) -> bool:
        return bool(self.token)

    async def _get(self, path: str, params: dict[str, Any] | None = None):
        if not self.token:
            raise RuntimeError("PANDASCORE_TOKEN is not configured")
        params = dict(params or {})
        params["token"] = self.token
        res = await self.client.get(f"{BASE}{path}", params=params)
        if res.status_code >= 400:
            raise RuntimeError(f"PandaScore {res.status_code}: {res.text[:300]}")
        return res.json()

    async def videogames(self, per_page: int = 100):
        return await self._get("/videogames", {"per_page": per_page})

    async def upcoming(self, game: str, per_page: int = 20):
        path = GAME_PATHS.get(game.lower(), game.lower())
        return await self._get(f"/{path}/matches/upcoming", {"per_page": per_page})

    async def player_stats(self, game: str, player_id_or_slug: str, games_count: int = 10):
        path = GAME_PATHS.get(game.lower(), game.lower())
        return await self._get(f"/{path}/players/{player_id_or_slug}/stats", {"games_count": games_count})
