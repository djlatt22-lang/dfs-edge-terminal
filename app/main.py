from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .demo import DEMO_ROWS, DEMO_SPORTS
from .services.math_utils import norm_cdf
from .services.model import grade_from_probability, sigma_for_market
from .services.odds_api import OddsApiClient
from .services.pandascore import FIXTURE_GAMES, PandaScoreClient

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.odds = OddsApiClient()
    app.state.panda = PandaScoreClient()
    yield
    await app.state.odds.close()
    await app.state.panda.close()


app = FastAPI(title="DFS Edge Terminal", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ImportedLine(BaseModel):
    provider: str = "Imported"
    sport: str
    player: str
    market: str
    line: float
    projection: float | None = None
    sigma: float | None = None
    matchup: str | None = None
    notes: str | None = None


class ImportPayload(BaseModel):
    rows: list[ImportedLine] = Field(default_factory=list, max_length=1000)


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "live_dfs_configured": app.state.odds.configured(),
        "esports_configured": app.state.panda.configured(),
    }


@app.get("/api/config")
async def config():
    return {
        "live_dfs_configured": app.state.odds.configured(),
        "esports_configured": app.state.panda.configured(),
        "dfs_providers": [
            {"key": "all", "label": "All DFS"},
            {"key": "prizepicks", "label": "PrizePicks"},
            {"key": "underdog", "label": "Underdog"},
            {"key": "dabble_us_dfs", "label": "Dabble"},
            {"key": "pick6", "label": "DraftKings Pick6"},
        ],
        "esports_games": FIXTURE_GAMES,
    }


@app.get("/api/sports")
async def sports(all_sports: bool = Query(False)):
    if not app.state.odds.configured():
        return {"mode": "demo", "sports": DEMO_SPORTS}
    try:
        data = await app.state.odds.sports(all_sports=all_sports)
        return {"mode": "live", "sports": data}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@app.get("/api/board")
async def board(
    sport: str = Query("americanfootball_nfl"),
    provider: str = Query("all"),
):
    if not app.state.odds.configured():
        rows = [r for r in DEMO_ROWS if sport in {"all", r["sport_key"]} and provider in {"all", r["provider_key"]}]
        return {"mode": "demo", "sport_key": sport, "rows": rows, "events_scanned": 3, "warnings": ["Demo mode: configure ODDS_API_KEY for live DFS lines."]}
    try:
        data = await app.state.odds.board(sport, provider=provider)
        data["mode"] = "live"
        return data
    except Exception as exc:
        raise HTTPException(502, str(exc))


@app.get("/api/esports/games")
async def esports_games():
    if not app.state.panda.configured():
        return {"mode": "fallback", "games": [{"slug": g, "name": g.upper()} for g in FIXTURE_GAMES]}
    try:
        games = await app.state.panda.videogames(per_page=100)
        normalized = [
            {"id": g.get("id"), "slug": g.get("slug"), "name": g.get("name") or g.get("slug")}
            for g in games if g.get("slug")
        ]
        return {"mode": "live", "games": normalized}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@app.get("/api/esports/upcoming")
async def esports_upcoming(game: str = Query("csgo"), limit: int = Query(20, ge=1, le=100)):
    if not app.state.panda.configured():
        return {
            "mode": "not_configured",
            "game": game,
            "matches": [],
            "message": "Add PANDASCORE_TOKEN for live esports schedules/stats. You can still import esports DFS lines on the Import tab.",
        }
    try:
        matches = await app.state.panda.upcoming(game, per_page=limit)
        return {"mode": "live", "game": game, "matches": matches}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@app.get("/api/esports/player-stats")
async def esports_player_stats(game: str, player: str, games_count: int = Query(10, ge=1, le=50)):
    if not app.state.panda.configured():
        raise HTTPException(400, "PANDASCORE_TOKEN is not configured")
    try:
        data = await app.state.panda.player_stats(game, player, games_count=games_count)
        return {"game": game, "player": player, "stats": data}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@app.post("/api/import/analyze")
async def analyze_import(payload: ImportPayload):
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(payload.rows):
        if row.projection is None:
            out.append({
                "id": f"import:{idx}", "provider": row.provider, "sport": row.sport, "player": row.player,
                "market": row.market, "market_label": row.market.replace("_", " ").title(), "line": row.line,
                "projection": None, "recommended_side": "NEEDS MODEL", "recommended_probability": None,
                "confidence": 0, "grade": "—", "edge": None, "edge_pct": None, "z_edge": None,
                "matchup": row.matchup or "Imported", "notes": [row.notes or "Add a projection, or connect a live statistical model/data feed."],
                "source_count": 0, "method": "imported line awaiting projection",
            })
            continue
        sigma = row.sigma or sigma_for_market(row.market, row.line, "Esports" if "esport" in row.sport.lower() else None)
        p_over = norm_cdf((row.projection - row.line) / sigma)
        p_under = 1 - p_over
        rec_side = "MORE" if p_over >= p_under else "LESS"
        rec_prob = max(p_over, p_under)
        edge = row.projection - row.line
        conf = round(min(92.0, 58 + min(22, abs(edge) / max(sigma, 1e-9) * 30)), 1)
        out.append({
            "id": f"import:{idx}", "provider": row.provider, "provider_key": "imported", "sport": row.sport, "sport_key": "imported",
            "player": row.player, "market": row.market, "market_label": row.market.replace("_", " ").title(), "line": row.line,
            "projection": round(row.projection, 3), "edge": round(edge, 3), "edge_pct": round(edge / max(abs(row.line), 1.0) * 100, 2),
            "z_edge": round(edge / max(sigma, 1e-9), 3), "over_probability": round(p_over * 100, 1), "under_probability": round(p_under * 100, 1),
            "recommended_side": rec_side, "recommended_probability": round(rec_prob * 100, 1), "confidence": conf,
            "grade": grade_from_probability(rec_prob, conf), "source_count": 1, "consensus_line": row.projection, "line_spread": 0,
            "sigma": round(sigma, 3), "matchup": row.matchup or "Imported", "notes": [row.notes] if row.notes else [], "books": [],
            "method": "user/imported projection → calibrated normal distribution",
        })
    out.sort(key=lambda x: x.get("recommended_probability") or 0, reverse=True)
    return {"rows": out}


@app.get("/{path:path}")
async def spa_fallback(path: str):
    candidate = STATIC / path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC / "index.html")
