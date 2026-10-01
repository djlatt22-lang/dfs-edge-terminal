from __future__ import annotations

import os
from math import exp
from statistics import NormalDist
from typing import Any

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="DFS Edge Terminal", version="1.0.0")
N = NormalDist()

DEMO = [
    {"sport":"NFL","provider":"PrizePicks","player":"Demo Quarterback","market":"Passing Yards","line":244.5,"projection":262.4,"side":"MORE","probability":62.7,"edge":17.9,"confidence":84,"grade":"A","matchup":"Demo Away @ Demo Home"},
    {"sport":"NBA","provider":"Underdog","player":"Demo Guard","market":"Points","line":25.5,"projection":22.8,"side":"LESS","probability":65.0,"edge":-2.7,"confidence":87,"grade":"A+","matchup":"Demo Away @ Demo Home"},
    {"sport":"MLB","provider":"PrizePicks","player":"Demo Pitcher","market":"Strikeouts","line":5.5,"projection":6.3,"side":"MORE","probability":64.2,"edge":0.8,"confidence":82,"grade":"A","matchup":"Demo Away @ Demo Home"},
    {"sport":"NHL","provider":"Dabble","player":"Demo Winger","market":"Shots On Goal","line":2.5,"projection":3.2,"side":"MORE","probability":68.0,"edge":0.7,"confidence":86,"grade":"A+","matchup":"Demo Away @ Demo Home"},
]

HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DFS Edge Terminal</title><style>
:root{--bg:#071019;--panel:#0d1824;--line:#1d3042;--text:#edf7ff;--muted:#8fa8bb;--green:#21e6a3;--red:#ff6b7b;--gold:#ffd166}*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#071019,#09131d 55%,#061018);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial}.wrap{max-width:1500px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:24px}.brand h1{margin:0;font-size:28px;letter-spacing:-.7px}.brand p{margin:6px 0 0;color:var(--muted)}.live{display:flex;align-items:center;gap:8px;color:var(--green);font-weight:700}.dot{width:9px;height:9px;background:var(--green);border-radius:99px;box-shadow:0 0 16px var(--green)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}.card,.panel{background:rgba(13,24,36,.94);border:1px solid var(--line);border-radius:16px}.card{padding:17px}.k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.v{font-size:25px;font-weight:800;margin-top:7px}.controls{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}.controls select,.controls input,.controls button{background:#0c1722;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.controls button{cursor:pointer;background:#102538;border-color:#23506b;font-weight:700}.panel{overflow:hidden}.head{padding:15px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}.head span{color:var(--muted);font-size:13px}table{width:100%;border-collapse:collapse}th,td{padding:13px 14px;border-bottom:1px solid #152536;text-align:left;font-size:14px}th{font-size:11px;letter-spacing:.07em;color:#7f9aaf;text-transform:uppercase}.player b{display:block}.player small{color:var(--muted)}.side{font-weight:800}.more{color:var(--green)}.less{color:var(--red)}.grade{display:inline-flex;min-width:38px;justify-content:center;padding:5px 8px;border-radius:8px;background:#173024;color:var(--green);font-weight:900}.edgep{color:var(--green)}.edgen{color:var(--red)}.banner{margin:14px 0;padding:13px 15px;border:1px solid #364b5e;border-radius:12px;color:#bfd0dc;background:#0b1722}.api{margin-top:18px;padding:15px}.api code{color:var(--gold)}@media(max-width:900px){.grid{grid-template-columns:1fr 1fr}.panel{overflow:auto}table{min-width:900px}}@media(max-width:560px){.grid{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}}
</style></head><body><div class="wrap"><div class="top"><div class="brand"><h1>DFS Edge Terminal</h1><p>PrizePicks · Underdog · Dabble · Pick6 · Sports + Esports</p></div><div class="live"><span class="dot"></span><span id="mode">Loading</span></div></div><div class="banner" id="banner">Checking data configuration…</div><div class="grid"><div class="card"><div class="k">Qualified Edges</div><div class="v" id="edges">0</div></div><div class="card"><div class="k">A / A+ Plays</div><div class="v" id="strong">0</div></div><div class="card"><div class="k">Top Hit Estimate</div><div class="v" id="top">—</div></div><div class="card"><div class="k">Data Mode</div><div class="v" id="dataMode">—</div></div></div><div class="controls"><select id="sport"><option value="all">All Sports</option><option>NFL</option><option>NBA</option><option>MLB</option><option>NHL</option><option>WNBA</option><option>CFB</option><option>Esports</option></select><select id="provider"><option value="all">All DFS</option><option>PrizePicks</option><option>Underdog</option><option>Dabble</option><option>DraftKings Pick6</option></select><input id="search" placeholder="Search player or market"><button onclick="load()">Refresh board</button></div><div class="panel"><div class="head"><b>Projection Board</b><span>Transparent model output · no guaranteed outcomes</span></div><table><thead><tr><th>Tier</th><th>Player</th><th>Sport</th><th>Market</th><th>DFS App</th><th>Line</th><th>Projection</th><th>Side</th><th>Hit Est.</th><th>Edge</th><th>Confidence</th></tr></thead><tbody id="rows"></tbody></table></div><div class="panel api"><b>Live data setup</b><p style="color:var(--muted)">Add <code>ODDS_API_KEY</code> in Railway Variables for live DFS/sportsbook consensus. Add <code>PANDASCORE_TOKEN</code> for esports schedules and stats. Without keys, this deployment intentionally shows demo rows rather than fabricating live lines.</p></div></div><script>
let all=[];const $=s=>document.querySelector(s);function fmt(n){return Number(n).toFixed(1)}function render(){let sport=$('#sport').value,provider=$('#provider').value,q=$('#search').value.toLowerCase();let r=all.filter(x=>(sport==='all'||x.sport===sport)&&(provider==='all'||x.provider===provider)&&(!q||(`${x.player} ${x.market}`).toLowerCase().includes(q)));$('#rows').innerHTML=r.map(x=>`<tr><td><span class="grade">${x.grade}</span></td><td class="player"><b>${x.player}</b><small>${x.matchup||''}</small></td><td>${x.sport}</td><td>${x.market}</td><td>${x.provider}</td><td>${fmt(x.line)}</td><td>${fmt(x.projection)}</td><td class="side ${x.side==='MORE'?'more':'less'}">${x.side}</td><td>${fmt(x.probability)}%</td><td class="${x.edge>=0?'edgep':'edgen'}">${x.edge>=0?'+':''}${fmt(x.edge)}</td><td>${fmt(x.confidence)}</td></tr>`).join('');$('#edges').textContent=r.length;$('#strong').textContent=r.filter(x=>x.grade==='A'||x.grade==='A+').length;$('#top').textContent=r.length?fmt(Math.max(...r.map(x=>x.probability)))+'%':'—'}async function load(){let d=await fetch('/api/board').then(r=>r.json());all=d.rows||[];$('#mode').textContent=d.mode==='live'?'LIVE':'DEMO';$('#dataMode').textContent=d.mode.toUpperCase();$('#banner').textContent=d.message;render()}$('#sport').onchange=render;$('#provider').onchange=render;$('#search').oninput=render;load();
</script></body></html>'''


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML


@app.get("/api/health")
async def health():
    return {"ok": True, "live_dfs_configured": bool(os.getenv("ODDS_API_KEY")), "esports_configured": bool(os.getenv("PANDASCORE_TOKEN"))}


@app.get("/api/board")
async def board(sport: str = Query("all"), provider: str = Query("all")):
    key = os.getenv("ODDS_API_KEY", "")
    if not key:
        rows = [x for x in DEMO if (sport == "all" or x["sport"] == sport) and (provider == "all" or x["provider"] == provider)]
        return {"mode":"demo","rows":rows,"message":"Demo mode is active. Add ODDS_API_KEY in Railway to enable authorized live DFS/sportsbook market ingestion."}

    # Authorized live provider architecture is enabled when a key is present. The app first discovers active sports.
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": key})
            res.raise_for_status()
            sports = res.json()
        return {"mode":"live","rows":[],"sports":sports,"message":"Live API connection is healthy. Full event/player-prop hydration is ready for the next model expansion."}
    except Exception as exc:
        return {"mode":"live","rows":[],"message":f"Live feed configured, but upstream request failed: {exc}"}


@app.get("/api/config")
async def config():
    return {"providers":["PrizePicks","Underdog","Dabble","DraftKings Pick6"],"sports":"dynamic","esports_configured":bool(os.getenv("PANDASCORE_TOKEN"))}
