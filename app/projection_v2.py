from __future__ import annotations
import csv, io, math, os, random, statistics
from contextlib import asynccontextmanager
from typing import Any
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

RT_BASE="https://api.rtsports.com"
SPORT_MAP={"nfl":"football","cfb":"football","nba":"basketball","wnba":"basketball","mlb":"baseball","nhl":"hockey","pga":"golf"}
SIGMA={"passing_yards":42,"rushing_yards":28,"receiving_yards":31,"pass_attempts":6,"rush_attempts":4.5,"receptions":2.2,"passing_tds":1.05,"points":7.5,"rebounds":3.4,"assists":3.0,"pra":9.5,"fantasy_score":9.0,"pitcher_strikeouts":2.2,"pitching_outs":3.8,"hits":1.0,"total_bases":1.7,"shots_on_goal":1.6,"saves":6.0,"goals":0.75,"birdies":3.5}

def sigma_for(market,line,sport):
    k=market.lower().replace(" ","_").replace("+","_")
    for key,val in SIGMA.items():
        if key in k:return float(val)
    return max(1.0,abs(line)*(0.18 if sport.lower() in {"nfl","cfb","nba","wnba","mlb","nhl","pga"} else 0.22))

def grade(p,conf):
    x=p*100
    if x>=68 and conf>=64:return "A+"
    if x>=63 and conf>=59:return "A"
    if x>=59:return "B+"
    if x>=55:return "B"
    return "C"

class RTSports:
    def __init__(self):
        self.token=os.getenv("DFS_SPORTS_TOKEN","").strip()
        self.client=httpx.AsyncClient(timeout=25,headers={"Accept":"application/json","User-Agent":"DFS-Projection-Lab/3.0"})
    async def close(self): await self.client.aclose()
    async def get(self,sport,resource):
        if not self.token: raise RuntimeError("DFS_SPORTS_TOKEN is not configured")
        upstream=SPORT_MAP.get(sport.lower(),sport.lower())
        url=f"{RT_BASE}/daily/{self.token}/{upstream}/{resource}"
        r=await self.client.get(url)
        if r.status_code>=400: raise RuntimeError(f"DFS sports API returned HTTP {r.status_code}")
        try:return r.json()
        except Exception: raise RuntimeError("DFS sports API returned a non-JSON response")
    async def ping(self):
        if not self.token:return False
        try:
            await self.get("nfl","period")
            return True
        except Exception:return False

@asynccontextmanager
async def lifespan(app):
    app.state.dfs=RTSports()
    yield
    await app.state.dfs.close()

app=FastAPI(title="DFS Projection Lab",version="3.0",lifespan=lifespan)

class ProjectionRequest(BaseModel):
    sport:str="NFL"
    player:str
    market:str
    line:float
    history:list[float]=Field(default_factory=list,max_length=100)
    base:float|None=None
    opponent:float=Field(0,ge=-50,le=50)
    role:float=Field(0,ge=-50,le=50)
    pace:float=Field(0,ge=-50,le=50)
    injury:float=Field(0,ge=-50,le=50)
    weather:float=Field(0,ge=-50,le=50)
    sims:int=Field(20000,ge=1000,le=100000)

def project(q:ProjectionRequest):
    vals=[float(x) for x in q.history if math.isfinite(float(x))]
    if q.base is None and not vals:raise ValueError("Enter historical results or a base projection.")
    if q.base is None:
        n=len(vals)
        weights=[1+0.45*(i/max(1,n-1)) for i in range(n)]
        recent=sum(v*w for v,w in zip(vals,weights))/sum(weights)
        med=statistics.median(vals)
        base=recent*.72+med*.28
    else: base=float(q.base)
    mult=1.0
    for adj in (q.opponent,q.role,q.pace,q.injury,q.weather): mult*=1+adj/100
    mu=base*mult
    prior=sigma_for(q.market,max(abs(q.line),abs(mu),1),q.sport)
    obs=statistics.stdev(vals) if len(vals)>1 else 0
    sd=max(.35,obs*.72+prior*.28) if obs else prior
    seed=20261023+len(vals)+int(abs(q.line)*100)+sum(ord(c) for c in q.player[:12])
    rng=random.Random(seed)
    over=sum(rng.gauss(mu,sd)>q.line for _ in range(q.sims))/q.sims
    under=1-over
    side="MORE" if over>=under else "LESS"
    p=max(over,under)
    edge=mu-q.line
    z=edge/max(sd,1e-9)
    conf=min(96,46+min(len(vals),20)*1.3+min(abs(z),2.2)*13)
    if q.base is not None and not vals:conf=min(conf,72)
    return {"player":q.player,"sport":q.sport,"market":q.market,"line":round(q.line,2),"projection":round(mu,2),"edge":round(edge,2),"sigma":round(sd,2),"more":round(over*100,1),"less":round(under*100,1),"side":side,"probability":round(p*100,1),"confidence":round(conf,1),"grade":grade(p,conf),"sample_size":len(vals),"simulations":q.sims}

HTML=r"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>DFS Projection Lab</title><style>
:root{--bg:#06090d;--p:#0d141c;--b:#22303c;--t:#eef5f7;--m:#7e8c97;--g:#c9ff52;--c:#63e7ff;--r:#ff6d7d}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 78% -15%,#112838,var(--bg) 38%);color:var(--t);font-family:Inter,system-ui,-apple-system,sans-serif}header{position:sticky;top:0;z-index:5;height:68px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:1px solid var(--b);background:#06090dea;backdrop-filter:blur(12px)}header b{letter-spacing:.14em}header small{display:block;color:var(--m)}.pill{font-size:11px;padding:7px 10px;border-radius:99px;border:1px solid var(--b);color:var(--m)}.good{color:var(--g);border-color:#4d6530}main{max-width:1260px;margin:auto;padding:32px}.hero{display:grid;grid-template-columns:1fr 290px;gap:24px;align-items:end}.hero h1{font-size:54px;line-height:.96;letter-spacing:-.055em;margin:8px 0 14px}.hero em{font-style:normal;color:var(--g)}.hero p,.muted{color:var(--m);line-height:1.6}.panel,.card{background:linear-gradient(180deg,#111a24,var(--p));border:1px solid var(--b);border-radius:14px;padding:20px}.card strong{display:block;font:900 31px ui-monospace,monospace;margin:9px 0}.tabs{display:flex;gap:6px;border-bottom:1px solid var(--b);margin:26px 0 16px;overflow:auto}.tabs button{white-space:nowrap;border:0;background:none;color:var(--m);padding:12px;cursor:pointer}.tabs .on{color:#fff;border-bottom:2px solid var(--g)}.view{display:none}.view.on{display:block}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}label{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--m)}input,select,textarea{width:100%;margin-top:6px;background:#070c12;border:1px solid #293744;border-radius:8px;padding:11px;color:white}textarea{height:90px}.wide{display:block;margin-top:10px}.btn{width:100%;margin-top:12px;padding:12px;border:1px solid var(--g);border-radius:8px;background:var(--g);color:#0a1007;font-weight:900;cursor:pointer}.result{margin-top:10px;padding:16px;border:1px solid var(--b);border-radius:10px}.result .prob{font:900 44px ui-monospace,monospace}.more{color:var(--g)}.less{color:var(--r)}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}.metrics div{border:1px solid var(--b);padding:11px;border-radius:8px}.metrics span{font-size:9px;color:var(--m);text-transform:uppercase}.metrics b{display:block;font:700 17px ui-monospace,monospace;margin-top:4px}.bar{height:8px;background:var(--r);border-radius:20px;overflow:hidden;margin-top:14px}.bar i{display:block;height:100%;background:var(--g);width:50%}.feed{margin-top:12px;overflow:auto;max-height:520px}.feed pre{font-size:11px;white-space:pre-wrap}.table{width:100%;border-collapse:collapse;font-size:12px}.table th,.table td{padding:10px;border-bottom:1px solid var(--b);text-align:left}.table th{color:var(--m);font-size:9px;text-transform:uppercase}.grade{color:var(--g);font-weight:900}.note{font-size:11px;line-height:1.55;color:var(--m);margin-top:10px}.toolbar{display:flex;gap:10px;align-items:end}.toolbar label{flex:1}.toolbar .btn{width:auto}.section p{color:var(--m)}@media(max-width:820px){main{padding:18px}.hero,.two{grid-template-columns:1fr}.hero h1{font-size:43px}.hero .card{display:none}.grid{grid-template-columns:1fr}.toolbar{display:grid}.toolbar .btn{width:100%}.metrics{grid-template-columns:repeat(2,1fr)}}</style></head><body>
<header><div><b>DFS//PROJECTION LAB</b><small>sports prop probability engine</small></div><span id="apiStatus" class="pill">Checking feed</span></header><main>
<section class="hero"><div><small>NO BLACK-BOX PICKS</small><h1>Project the stat.<br><em>Measure the edge.</em></h1><p>Sports-only DFS modeling for NFL, college football, NBA, WNBA, MLB, NHL and PGA. Recent form is weighted, context adjustments are explicit, and every selection gets a 20,000-run Monte Carlo hit-rate estimate.</p></div><div class="card"><small>LAST MODEL CALL</small><strong id="heroPick">—</strong><small id="heroMeta">Run your first projection</small></div></section>
<div class="tabs"><button class="on" data-view="lab">Projection Lab</button><button data-view="feed">DFS Sports Feed</button><button data-view="batch">Batch Board</button><button data-view="method">Method</button></div>
<section id="lab" class="view on"><div class="two"><div class="panel"><h2>Player projection</h2><div class="grid"><label>Sport<select id="sport"><option>NFL</option><option>CFB</option><option>NBA</option><option>WNBA</option><option>MLB</option><option>NHL</option><option>PGA</option></select></label><label>Player<input id="player" placeholder="Player name"></label><label>Market<input id="market" placeholder="passing_yards / points / strikeouts"></label><label>DFS line<input id="line" type="number" step=".1"></label></div><label class="wide">Historical results — oldest to newest<textarea id="history" placeholder="231,268,249,291,257,276"></textarea></label><div class="grid"><label>Opponent %<input id="opp" type="number" value="0" step=".5"></label><label>Role/volume %<input id="role" type="number" value="0" step=".5"></label><label>Pace/game env. %<input id="pace" type="number" value="0" step=".5"></label><label>Injury/availability %<input id="injury" type="number" value="0" step=".5"></label><label>Weather %<input id="weather" type="number" value="0" step=".5"></label><label>Optional base projection<input id="base" type="number" step=".1" placeholder="Leave blank"></label></div><button id="run" class="btn">Run 20,000 simulations</button><div class="note">Adjustments are multiplicative and visible. The model never invents a missing line, player history, injury, or matchup input.</div></div>
<div class="panel"><h2 id="name">Model output</h2><div class="result"><div id="side">—</div><div id="prob" class="prob">—</div><small>modeled hit probability</small></div><div class="metrics"><div><span>Projection</span><b id="proj">—</b></div><div><span>Line</span><b id="rline">—</b></div><div><span>Edge</span><b id="edge">—</b></div><div><span>Volatility</span><b id="sd">—</b></div><div><span>Confidence</span><b id="conf">—</b></div><div><span>Grade</span><b id="grade">—</b></div></div><div class="bar"><i id="bar"></i></div><div id="split" class="note">LESS — · MORE —</div></div></div></section>
<section id="feed" class="view section"><h2>DFS sports feed</h2><p>The API token is held only on the server. This panel checks the upstream DFS sports feed without exposing the key to the browser.</p><div class="panel toolbar"><label>Sport<select id="feedSport"><option value="nfl">NFL</option><option value="cfb">CFB</option><option value="nba">NBA</option><option value="wnba">WNBA</option><option value="mlb">MLB</option><option value="nhl">NHL</option><option value="pga">PGA</option></select></label><label>Feed<select id="resource"><option value="period">Slate / period</option><option value="contests">Contests</option></select></label><button id="loadFeed" class="btn">Load live feed</button></div><div class="panel feed"><pre id="feedOut">Choose a sport and load the feed.</pre></div><div class="note">Upstream coverage varies by sport and account. Empty or unsupported results are shown as-is rather than replaced with fake data.</div></section>
<section id="batch" class="view section"><h2>Batch-board analyzer</h2><p>Paste CSV rows and score multiple props through the same projection engine.</p><div class="panel"><textarea id="csv" style="height:170px" placeholder="sport,player,market,line,history,opponent,role,pace,injury,weather&#10;NFL,Player Name,passing_yards,245.5,&quot;231|268|249|291|257&quot;,2,5,1,0,-1"></textarea><button id="batchRun" class="btn">Analyze board</button><div id="batchOut" class="feed"></div></div></section>
<section id="method" class="view section"><h2>How the model works</h2><div class="two"><div class="panel"><h3>Projection</h3><p>Recent results receive modest extra weight, then the weighted estimate is blended with the median to reduce the influence of single-game outliers.</p><h3>Context</h3><p>Opponent, role/volume, pace, injury/availability and weather are separate inputs. Nothing is silently baked in.</p></div><div class="panel"><h3>Probability</h3><p>Observed volatility is blended with a market-specific prior. The engine simulates 20,000 outcomes and reports MORE/LESS probability, edge, confidence and grade.</p><h3>Guardrail</h3><p>A grade measures model strength, not certainty. Verify the actual DFS line, starting role, injuries and game environment before using any play.</p></div></div></section>
</main><script>
const $=id=>document.getElementById(id),fmt=(x,d=1)=>x==null?"—":Number(x).toFixed(d);
document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));document.querySelectorAll(".view").forEach(x=>x.classList.remove("on"));b.classList.add("on");$(b.dataset.view).classList.add("on")});
fetch("/api/health").then(r=>r.json()).then(d=>{apiStatus.textContent=d.feed_configured?(d.feed_reachable?"DFS feed connected":"Key configured · feed check failed"):"DFS token missing";if(d.feed_configured)apiStatus.classList.add("good")}).catch(()=>apiStatus.textContent="API offline");
run.onclick=async()=>{const hist=history.value.split(",").map(Number).filter(Number.isFinite),bv=base.value.trim();const q={sport:sport.value,player:player.value||"Player",market:market.value||"prop",line:Number(line.value),history:hist,base:bv===""?null:Number(bv),opponent:Number(opp.value||0),role:Number(role.value||0),pace:Number(pace.value||0),injury:Number(injury.value||0),weather:Number(weather.value||0),sims:20000};if(!Number.isFinite(q.line))return alert("Enter a DFS line");run.disabled=true;run.textContent="Simulating…";try{const r=await fetch("/api/project",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(q)}),d=await r.json();if(!r.ok)throw Error(d.detail||"Projection failed");name.textContent=d.player+" · "+d.market.replaceAll("_"," ");side.textContent=d.side;side.className=d.side==="MORE"?"more":"less";prob.textContent=fmt(d.probability)+"%";proj.textContent=fmt(d.projection);rline.textContent=fmt(d.line);edge.textContent=(d.edge>0?"+":"")+fmt(d.edge);sd.textContent=fmt(d.sigma);conf.textContent=fmt(d.confidence,0)+"%";grade.textContent=d.grade;bar.style.width=d.more+"%";split.textContent="LESS "+fmt(d.less)+"% · MORE "+fmt(d.more)+"%";heroPick.textContent=d.side+" "+fmt(d.line);heroMeta.textContent=d.player+" · "+fmt(d.probability)+"% · Grade "+d.grade}catch(e){alert(e.message)}finally{run.disabled=false;run.textContent="Run 20,000 simulations"}};
loadFeed.onclick=async()=>{feedOut.textContent="Loading…";try{const r=await fetch("/api/dfs/feed?sport="+feedSport.value+"&resource="+resource.value),d=await r.json();if(!r.ok)throw Error(d.detail||"Feed failed");feedOut.textContent=JSON.stringify(d.data,null,2)}catch(e){feedOut.textContent=e.message}};
batchRun.onclick=async()=>{batchOut.innerHTML="Running…";try{const r=await fetch("/api/batch",{method:"POST",headers:{"Content-Type":"text/plain"},body:csv.value}),d=await r.json();if(!r.ok)throw Error(d.detail||"Batch failed");batchOut.innerHTML="<table class=table><thead><tr><th>Grade</th><th>Player</th><th>Market</th><th>Line</th><th>Projection</th><th>Side</th><th>Prob.</th></tr></thead><tbody>"+d.results.map(x=>"<tr><td class=grade>"+x.grade+"</td><td>"+x.player+"</td><td>"+x.market+"</td><td>"+x.line+"</td><td>"+x.projection+"</td><td>"+x.side+"</td><td>"+x.probability+"%</td></tr>").join("")+"</tbody></table>"}catch(e){batchOut.textContent=e.message}};
</script></body></html>"""

@app.get("/",response_class=HTMLResponse)
async def home():return HTMLResponse(HTML)

@app.get("/api/health")
async def health():
    reachable=await app.state.dfs.ping() if app.state.dfs.token else False
    return {"ok":True,"site":"DFS Projection Lab","feed_configured":bool(app.state.dfs.token),"feed_reachable":reachable}

@app.post("/api/project")
async def project_endpoint(q:ProjectionRequest):
    try:return project(q)
    except ValueError as e:raise HTTPException(400,str(e))

@app.get("/api/dfs/feed")
async def dfs_feed(sport:str="nfl",resource:str=Query("period",pattern="^(period|contests)$")):
    try:return {"sport":sport,"resource":resource,"data":await app.state.dfs.get(sport,resource)}
    except Exception as e:raise HTTPException(502,str(e))

@app.post("/api/batch")
async def batch(body:str):
    try:
        reader=csv.DictReader(io.StringIO(body.strip()))
        out=[]
        for row in reader:
            hist=[float(x.strip()) for x in (row.get("history") or "").replace(",","|").split("|") if x.strip()]
            q=ProjectionRequest(
                sport=row.get("sport") or "NFL",player=row.get("player") or "Player",market=row.get("market") or "prop",
                line=float(row["line"]),history=hist,
                opponent=float(row.get("opponent") or 0),role=float(row.get("role") or 0),pace=float(row.get("pace") or 0),
                injury=float(row.get("injury") or 0),weather=float(row.get("weather") or 0)
            )
            out.append(project(q))
        out.sort(key=lambda x:(x["grade"]=="A+",x["probability"]),reverse=True)
        return {"count":len(out),"results":out}
    except Exception as e:raise HTTPException(400,f"Invalid CSV: {e}")
