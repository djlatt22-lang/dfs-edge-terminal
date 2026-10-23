from __future__ import annotations
import math, os, random, statistics
from contextlib import asynccontextmanager
from typing import Any
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

BASE="https://api.pandascore.co"
GAME={"cs2":"csgo","csgo":"csgo","lol":"lol","dota2":"dota2","valorant":"valorant"}
SIGMA={"passing_yards":42,"rushing_yards":28,"receiving_yards":31,"pass_attempts":6,"rush_attempts":4.5,"receptions":2.2,"points":7.5,"rebounds":3.4,"assists":3,"fantasy_score":9,"pitcher_strikeouts":2.2,"shots_on_goal":1.6,"saves":6,"kills":5.5,"headshots":4.5}

def sig(m,l,s):
    k=m.lower().replace(" ","_")
    for a,v in SIGMA.items():
        if a in k:return float(v)
    return max(1.0,abs(l)*(0.18 if s.lower() in {"nfl","cfb","nba","wnba","mlb","nhl"} else 0.22))

def grade(p,c):
    x=p*100
    if x>=67 and c>=62:return "A+"
    if x>=62 and c>=58:return "A"
    if x>=58:return "B+"
    if x>=54:return "B"
    return "C"

class Panda:
    def __init__(self):
        self.token=os.getenv("PANDASCORE_TOKEN","")
        h={"Accept":"application/json","User-Agent":"DFS-Projection-Lab/2.0"}
        if self.token:h["Authorization"]=f"Bearer {self.token}"
        self.c=httpx.AsyncClient(timeout=25,headers=h)
    async def close(self):await self.c.aclose()
    async def get(self,path,params=None):
        if not self.token:raise RuntimeError("PANDASCORE_TOKEN is not configured")
        r=await self.c.get(BASE+path,params=params or {})
        if r.status_code>=400:
            msg=r.text[:300]
            if r.status_code==403:msg="Your PandaScore plan does not include this detailed-stat endpoint. Upcoming fixtures still work on all plans."
            raise RuntimeError(f"PandaScore {r.status_code}: {msg}")
        return r.json()

@asynccontextmanager
async def life(app):
    app.state.p=Panda();yield;await app.state.p.close()

app=FastAPI(title="DFS Projection Lab",version="2.0",lifespan=life)

class Req(BaseModel):
    sport:str="Other";player:str;market:str;line:float
    history:list[float]=Field(default_factory=list,max_length=100)
    base:float|None=None
    opponent:float=Field(0,ge=-50,le=50)
    role:float=Field(0,ge=-50,le=50)
    pace:float=Field(0,ge=-50,le=50)
    sims:int=Field(20000,ge=1000,le=100000)

def model(q:Req):
    vals=[float(x) for x in q.history if math.isfinite(float(x))]
    if q.base is None and not vals:raise ValueError("Enter historical values or a base projection.")
    if q.base is None:
        n=len(vals);w=[1+.35*(i/max(n-1,1)) for i in range(n)]
        recent=sum(v*x for v,x in zip(vals,w))/sum(w)
        base=recent*.72+statistics.median(vals)*.28
    else:base=float(q.base)
    proj=base*(1+q.opponent/100)*(1+q.role/100)*(1+q.pace/100)
    prior=sig(q.market,max(abs(q.line),abs(proj),1),q.sport)
    obs=statistics.stdev(vals) if len(vals)>1 else 0
    sd=max(.35,obs*.72+prior*.28) if obs else prior
    rng=random.Random(20261023+len(vals)+int(abs(q.line)*10))
    over=sum(rng.gauss(proj,sd)>q.line for _ in range(q.sims))/q.sims
    under=1-over;side="MORE" if over>=under else "LESS";p=max(over,under);edge=proj-q.line;z=edge/max(sd,1e-9)
    conf=min(95,48+min(len(vals),20)*1.25+min(abs(z),2)*13)
    if q.base is not None and not vals:conf=min(conf,72)
    return {"player":q.player,"market":q.market,"line":round(q.line,2),"projection":round(proj,2),"edge":round(edge,2),"sigma":round(sd,2),"over":round(over*100,1),"under":round(under*100,1),"side":side,"prob":round(p*100,1),"confidence":round(conf,1),"grade":grade(p,conf),"sample":len(vals),"sims":q.sims}

HTML=r"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>DFS Projection Lab</title><style>
:root{--b:#070a0f;--p:#0e151e;--l:#22303d;--t:#edf5f7;--m:#7b8b98;--g:#c9ff52;--c:#60e6ff;--r:#ff7280}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 70% -10%,#102333,var(--b) 35%);color:var(--t);font-family:system-ui,-apple-system,sans-serif}header{height:68px;border-bottom:1px solid var(--l);display:flex;align-items:center;justify-content:space-between;padding:0 24px;position:sticky;top:0;background:#070a0fe8;backdrop-filter:blur(12px)}header b{letter-spacing:.13em}header small{color:var(--m);display:block}.pill{border:1px solid var(--l);border-radius:99px;padding:7px 10px;font-size:11px;color:var(--m)}.live{color:var(--g);border-color:#4d632d}main{max-width:1250px;margin:auto;padding:32px}.hero{display:grid;grid-template-columns:1fr 280px;gap:20px;align-items:end}.hero h1{font-size:52px;line-height:.98;letter-spacing:-.05em;margin:8px 0 12px}.hero em{font-style:normal;color:var(--g)}.hero p{color:var(--m);line-height:1.65}.card,.panel{background:linear-gradient(180deg,#111a24,var(--p));border:1px solid var(--l);border-radius:14px;padding:20px}.card strong{display:block;font:800 30px ui-monospace,monospace;margin:10px 0}.tabs{display:flex;gap:6px;border-bottom:1px solid var(--l);margin:24px 0 16px}.tabs button{background:none;border:0;color:var(--m);padding:12px;cursor:pointer}.tabs .on{color:#fff;border-bottom:2px solid var(--g)}.view{display:none}.view.on{display:block}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}label{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--m)}input,select,textarea{width:100%;margin-top:6px;background:#080d13;border:1px solid #293744;border-radius:8px;padding:11px;color:#fff}textarea{height:90px}.wide{display:block;margin-top:10px}.btn{width:100%;margin-top:12px;padding:12px;border:1px solid var(--g);background:var(--g);color:#0b1008;border-radius:8px;font-weight:800;cursor:pointer}.result{border:1px solid var(--l);border-radius:10px;padding:16px;margin-top:12px}.result .side{font-size:13px;font-weight:900}.result .prob{font:900 42px ui-monospace,monospace;margin:3px 0}.more{color:var(--g)}.less{color:var(--r)}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}.metrics div{border:1px solid var(--l);padding:11px;border-radius:8px}.metrics span{font-size:9px;color:var(--m);text-transform:uppercase}.metrics b{display:block;margin-top:5px;font:700 17px ui-monospace,monospace}.bar{height:8px;background:var(--r);border-radius:20px;overflow:hidden;margin-top:14px}.bar i{display:block;height:100%;background:var(--g);width:50%}.section h2{margin-bottom:5px}.section p{color:var(--m)}.toolbar{display:flex;gap:10px;align-items:end}.toolbar label{flex:1}.toolbar .btn{width:auto}.fixtures{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.fixture{background:var(--p);border:1px solid var(--l);border-radius:10px;padding:15px}.fixture small{color:var(--m)}pre{white-space:pre-wrap;max-height:330px;overflow:auto;background:#070b10;border:1px solid var(--l);padding:12px;border-radius:8px;font-size:10px}.note{color:var(--m);font-size:11px;line-height:1.6;margin-top:12px}@media(max-width:800px){main{padding:18px}.hero,.two{grid-template-columns:1fr}.hero .card{display:none}.hero h1{font-size:42px}.fixtures{grid-template-columns:1fr}.grid{grid-template-columns:1fr}.toolbar{display:grid}.toolbar .btn{width:100%}}</style></head><body>
<header><div><b>PROJECTION//LAB</b><small>DFS probability engine</small></div><span id="status" class="pill">Checking API</span></header><main>
<section class="hero"><div><small>DFS MODELING WORKBENCH</small><h1>Build the projection.<br><em>Measure the edge.</em></h1><p>Universal player-prop modeling with recent-weighted history, transparent matchup/role/pace adjustments, Monte Carlo hit rates, and live PandaScore esports fixtures.</p></div><div class="card"><small>TOP OUTPUT</small><strong id="heroPick">—</strong><small id="heroMeta">Run a projection</small></div></section>
<div class="tabs"><button class="on" data-v="lab">Projection Lab</button><button data-v="es">Live Esports</button><button data-v="about">Method</button></div>
<section id="lab" class="view on"><div class="two"><div class="panel"><h2>Player projection</h2><div class="grid"><label>Sport<select id="sport"><option>NFL</option><option>CFB</option><option>NBA</option><option>WNBA</option><option>MLB</option><option>NHL</option><option>Esports</option><option>Other</option></select></label><label>Player<input id="player" placeholder="Player name"></label><label>Market<input id="market" placeholder="passing_yards / kills"></label><label>DFS line<input id="line" type="number" step=".1"></label></div><label class="wide">Historical values — oldest to newest<textarea id="history" placeholder="231,268,249,291,257,276"></textarea></label><div class="grid"><label>Opponent adj. %<input id="opp" type="number" value="0" step=".5"></label><label>Role/volume adj. %<input id="role" type="number" value="0" step=".5"></label><label>Pace/game adj. %<input id="pace" type="number" value="0" step=".5"></label><label>Optional base projection<input id="base" type="number" step=".1" placeholder="Leave blank"></label></div><button id="run" class="btn">Run 20,000 simulations</button><div class="note">Positive adjustments raise the projection; negative adjustments lower it. Missing data is never fabricated.</div></div>
<div class="panel"><h2 id="name">Model output</h2><div class="result"><div id="side" class="side">—</div><div id="prob" class="prob">—</div><small>modeled hit probability</small></div><div class="metrics"><div><span>Projection</span><b id="proj">—</b></div><div><span>Line</span><b id="rline">—</b></div><div><span>Edge</span><b id="edge">—</b></div><div><span>Volatility</span><b id="sd">—</b></div><div><span>Confidence</span><b id="conf">—</b></div><div><span>Grade</span><b id="grade">—</b></div></div><div class="bar"><i id="bar"></i></div><div class="note" id="split">LESS — · MORE —</div></div></div></section>
<section id="es" class="view section"><h2>Live esports slate</h2><p>The API key stays on the server. Fixtures work on all PandaScore plans; detailed player stats may require a Historical plan.</p><div class="panel toolbar"><label>Game<select id="game"><option value="csgo">CS2</option><option value="lol">League of Legends</option><option value="dota2">Dota 2</option><option value="valorant">Valorant</option></select></label><button id="fixturesBtn" class="btn">Load fixtures</button></div><div id="fixtures" class="fixtures"></div><div class="panel" style="margin-top:12px"><h3>Player stats lookup</h3><div class="grid"><label>Player ID / slug<input id="esPlayer"></label><label>Game<select id="esGame"><option value="csgo">CS2</option><option value="lol">LoL</option><option value="dota2">Dota 2</option><option value="valorant">Valorant</option></select></label></div><button id="statsBtn" class="btn">Fetch player data</button><pre id="stats">Enter a PandaScore player ID or slug.</pre></div></section>
<section id="about" class="view section"><h2>Method</h2><div class="two"><div class="panel"><h3>Projection</h3><p>Recent observations get modest extra weight, then the result is blended with the median to reduce outlier sensitivity.</p><h3>Context</h3><p>Opponent, role/volume and pace adjustments are explicit so you can see every assumption.</p></div><div class="panel"><h3>Probability</h3><p>Observed volatility is blended with a market prior, then 20,000 Monte Carlo draws estimate MORE/LESS hit rates.</p><h3>Guardrail</h3><p>The grade is model strength, not a guarantee. Verify line, role, injuries and matchup before using a projection.</p></div></div></section>
</main><script>
const $=x=>document.getElementById(x),f=(x,d=1)=>x==null?"—":Number(x).toFixed(d);
document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));document.querySelectorAll(".view").forEach(x=>x.classList.remove("on"));b.classList.add("on");$(b.dataset.v).classList.add("on")});
fetch("/api/health").then(r=>r.json()).then(d=>{status.textContent=d.esports_configured?"PandaScore connected":"API key missing";if(d.esports_configured)status.classList.add("live")}).catch(()=>status.textContent="API offline");
run.onclick=async()=>{let h=history.value.split(",").map(Number).filter(Number.isFinite),bv=base.value.trim();let q={sport:sport.value,player:player.value||"Player",market:market.value||"prop",line:Number(line.value),history:h,base:bv===""?null:Number(bv),opponent:Number(opp.value||0),role:Number(role.value||0),pace:Number(pace.value||0),sims:20000};if(!Number.isFinite(q.line))return alert("Enter a DFS line");run.disabled=true;run.textContent="Simulating…";try{let r=await fetch("/api/project",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(q)}),d=await r.json();if(!r.ok)throw Error(d.detail||"Projection failed");name.textContent=d.player+" · "+d.market.replaceAll("_"," ");side.textContent=d.side;side.className="side "+(d.side==="MORE"?"more":"less");prob.textContent=f(d.prob)+"%";proj.textContent=f(d.projection);rline.textContent=f(d.line);edge.textContent=(d.edge>0?"+":"")+f(d.edge);sd.textContent=f(d.sigma);conf.textContent=f(d.confidence,0)+"%";grade.textContent=d.grade;bar.style.width=d.over+"%";split.textContent="LESS "+f(d.under)+"% · MORE "+f(d.over)+"%";heroPick.textContent=d.side+" "+f(d.line);heroMeta.textContent=d.player+" · "+f(d.prob)+"% · Grade "+d.grade}catch(e){alert(e.message)}finally{run.disabled=false;run.textContent="Run 20,000 simulations"}};
fixturesBtn.onclick=async()=>{fixtures.innerHTML="<div class=fixture>Loading…</div>";try{let r=await fetch("/api/esports/upcoming?game="+game.value+"&limit=24"),d=await r.json();if(!r.ok)throw Error(d.detail);fixtures.innerHTML=(d.matches||[]).map(m=>{let n=(m.opponents||[]).map(x=>x.opponent?.name).filter(Boolean).join(" vs ")||m.name||"TBD";return "<div class=fixture><small>"+(m.league?.name||"Esports")+"</small><h3>"+n+"</h3><p>"+(m.begin_at?new Date(m.begin_at).toLocaleString():"Start TBD")+"</p></div>"}).join("")||"<div class=fixture>No fixtures returned.</div>"}catch(e){fixtures.innerHTML="<div class=fixture>"+e.message+"</div>"}};
statsBtn.onclick=async()=>{if(!esPlayer.value.trim())return alert("Enter a player ID or slug");stats.textContent="Loading…";try{let r=await fetch("/api/esports/stats?game="+esGame.value+"&player="+encodeURIComponent(esPlayer.value.trim())),d=await r.json();if(!r.ok)throw Error(d.detail);stats.textContent=JSON.stringify(d,null,2)}catch(e){stats.textContent=e.message}};
</script></body></html>"""

@app.get("/",response_class=HTMLResponse)
async def home():return HTMLResponse(HTML)
@app.get("/api/health")
async def health():return {"ok":True,"site":"DFS Projection Lab","esports_configured":bool(app.state.p.token)}
@app.post("/api/project")
async def project(q:Req):
    try:return model(q)
    except ValueError as e:raise HTTPException(400,str(e))
@app.get("/api/esports/upcoming")
async def upcoming(game:str="csgo",limit:int=Query(20,ge=1,le=100)):
    try:return {"matches":await app.state.p.get(f"/{GAME.get(game,game)}/matches/upcoming",{"per_page":limit})}
    except Exception as e:raise HTTPException(502,str(e))
@app.get("/api/esports/stats")
async def stats(game:str,player:str):
    try:return {"stats":await app.state.p.get(f"/{GAME.get(game,game)}/players/{player}/stats",{"games_count":10})}
    except Exception:
        try:return {"note":"Detailed stats unavailable on this PandaScore plan; showing recent matches instead.","matches":await app.state.p.get(f"/players/{player}/matches",{"per_page":10})}
        except Exception as e:raise HTTPException(502,str(e))
