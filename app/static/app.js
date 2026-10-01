const state = { rows: [], filtered: [], config: null, sports: [] };
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

function toast(msg){ const t=$('#toast'); t.textContent=msg; t.classList.remove('hidden'); setTimeout(()=>t.classList.add('hidden'),3200); }
function esc(s){ return String(s ?? '').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function fmt(v,d=1){ return v===null||v===undefined||Number.isNaN(Number(v))?'—':Number(v).toFixed(d); }
function clock(){ $('#clock').textContent=new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}); }
setInterval(clock,1000); clock();

async function api(url, opts){ const r=await fetch(url,opts); if(!r.ok){let msg=`HTTP ${r.status}`; try{const j=await r.json();msg=j.detail||msg}catch{} throw new Error(msg)} return r.json(); }

function switchView(name){
  $$('.view').forEach(v=>v.classList.remove('active'));
  $$('.nav-item').forEach(v=>v.classList.toggle('active',v.dataset.view===name));
  $(`#${name}View`).classList.add('active');
}
$$('.nav-item').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));

async function init(){
  try{
    const [config, health, sports, egames] = await Promise.all([api('/api/config'), api('/api/health'), api('/api/sports'), api('/api/esports/games')]);
    state.config=config; state.sports=sports.sports||[]; state.esportsGames=egames.games||[];
    $('#oddsDot').classList.toggle('on',health.live_dfs_configured);
    $('#pandaDot').classList.toggle('on',health.esports_configured);
    $('#dataMode').textContent=health.live_dfs_configured?'LIVE DATA READY':'DEMO MODE';
    $('#dataMode').className='pill '+(health.live_dfs_configured?'live':'muted');
    fillSelects();
    await loadBoard();
  }catch(e){ toast(e.message); }
}

function fillSelects(){
  const s=$('#sportSelect'); s.innerHTML='';
  const grouped={};
  state.sports.filter(x=>x.active!==false && !String(x.key).includes('_winner')).forEach(x=>{(grouped[x.group||'Other']??=[]).push(x)});
  Object.entries(grouped).forEach(([g,arr])=>{ const og=document.createElement('optgroup');og.label=g; arr.forEach(x=>{const o=document.createElement('option');o.value=x.key;o.textContent=x.title;og.appendChild(o)});s.appendChild(og); });
  const preferred=['americanfootball_nfl','americanfootball_ncaaf','basketball_nba','baseball_mlb','icehockey_nhl'];
  const first=preferred.find(k=>state.sports.some(x=>x.key===k))||state.sports[0]?.key; if(first)s.value=first;
  $('#providerSelect').innerHTML=state.config.dfs_providers.map(x=>`<option value="${esc(x.key)}">${esc(x.label)}</option>`).join('');
  const games=(state.esportsGames&&state.esportsGames.length)?state.esportsGames:state.config.esports_games.map(x=>({slug:x,name:x.toUpperCase()}));
  $('#gameSelect').innerHTML=games.map(x=>`<option value="${esc(x.slug)}">${esc(x.name||x.slug)}</option>`).join('');
}

async function loadBoard(){
  const sport=$('#sportSelect').value, provider=$('#providerSelect').value;
  $('#loading').classList.remove('hidden'); $('#emptyState').classList.add('hidden');
  $('#refreshBtn').disabled=true;
  try{
    const d=await api(`/api/board?sport=${encodeURIComponent(sport)}&provider=${encodeURIComponent(provider)}`);
    state.rows=d.rows||[];
    $('#tableSub').textContent=`${d.events_scanned||0} events scanned · ${d.mode==='live'?'live feed':'demo sample'} · click any row for evidence`;
    if(d.warnings?.length && d.mode==='live') toast(d.warnings[0]);
    applyFilters();
    $('#freshness').textContent=new Date().toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
  }catch(e){ toast(e.message); state.rows=[]; applyFilters(); }
  finally{$('#loading').classList.add('hidden');$('#refreshBtn').disabled=false;}
}

function applyFilters(){
  const min=Number($('#probSelect').value||0); const q=$('#searchInput').value.trim().toLowerCase();
  state.filtered=state.rows.filter(r=>(r.recommended_probability??0)>=min && (!q || `${r.player} ${r.market_label} ${r.matchup}`.toLowerCase().includes(q)));
  renderRows('#boardBody',state.filtered);
  $('#emptyState').classList.toggle('hidden',state.filtered.length>0);
  $('#edgeCount').textContent=state.filtered.length;
  $('#strongCount').textContent=state.filtered.filter(r=>['A','A+'].includes(r.grade)).length;
  $('#avgSources').textContent=state.filtered.length?fmt(state.filtered.reduce((a,b)=>a+(b.source_count||0),0)/state.filtered.length,1):'0.0';
  const top=state.filtered[0]; $('#topEdge').textContent=top?`${fmt(top.recommended_probability,1)}%`:'—'; $('#topEdgeMeta').textContent=top?`${top.player} · ${top.recommended_side} ${top.line}`:'No rows above threshold';
}

function gradeClass(g){return g==='A+'?'ap':g==='A'?'a':'b'}
function renderRows(sel,rows){
  const body=$(sel); body.innerHTML=rows.map(r=>`<tr data-id="${esc(r.id)}">
    <td><span class="grade ${gradeClass(r.grade)}">${esc(r.grade)}</span></td>
    <td class="player-cell"><b>${esc(r.player)}</b><span>${esc(r.matchup||r.sport)}</span></td>
    <td>${esc(r.market_label||r.market)}</td>
    <td>${esc(r.provider)}</td>
    <td class="mono">${fmt(r.line,1)}</td>
    <td class="mono">${fmt(r.projection,1)}</td>
    <td><span class="side ${String(r.recommended_side).toLowerCase()==='more'?'more':'less'}">${esc(r.recommended_side)}</span></td>
    <td class="mono">${r.recommended_probability==null?'—':fmt(r.recommended_probability,1)+'%'}</td>
    <td class="mono ${Number(r.edge)>=0?'edge-pos':'edge-neg'}">${r.edge==null?'—':(Number(r.edge)>=0?'+':'')+fmt(r.edge,2)}</td>
    <td class="mono">${fmt(r.confidence,0)}</td><td><span class="source-badge">${r.source_count||0} bk</span></td>
  </tr>`).join('');
  body.querySelectorAll('tr').forEach(tr=>tr.addEventListener('click',()=>{const all=[...state.rows,...(window.importRows||[])];const r=all.find(x=>String(x.id)===tr.dataset.id);if(r)openDrawer(r)}));
}

function openDrawer(r){
  const books=(r.books||[]).map(b=>`<div class="book-row"><span>${esc(b.book)}</span><span class="mono">${fmt(b.line,1)}</span><span class="mono">${esc(b.over??'—')}</span><span class="mono">${esc(b.under??'—')}</span></div>`).join('')||'<div class="note">No sportsbook evidence attached to this imported/demo row.</div>';
  $('#drawerContent').innerHTML=`<div class="drawer-inner"><div class="drawer-kicker">${esc(r.provider)} · ${esc(r.sport)}</div><div class="drawer-title">${esc(r.player)}</div><div class="drawer-sub">${esc(r.market_label||r.market)} · ${esc(r.matchup||'')}</div>
    <div class="drawer-call"><div class="box"><div class="box-label">Model call</div><div class="box-value ${String(r.recommended_side).toLowerCase()==='more'?'edge-pos':'edge-neg'}">${esc(r.recommended_side)} ${fmt(r.line,1)}</div></div><div class="box"><div class="box-label">Hit estimate</div><div class="box-value">${r.recommended_probability==null?'—':fmt(r.recommended_probability,1)+'%'}</div></div><div class="box"><div class="box-label">Projection</div><div class="box-value">${fmt(r.projection,2)}</div></div><div class="box"><div class="box-label">Consensus line</div><div class="box-value">${fmt(r.consensus_line,2)}</div></div></div>
    <div class="drawer-section"><div class="section-title">Model diagnostics</div><div class="method-list"><div><span>Δ</span><p>Raw edge: <b>${r.edge==null?'—':fmt(r.edge,3)}</b> · standardized: <b>${fmt(r.z_edge,3)}σ</b></p></div><div><span>σ</span><p>Modeled volatility: <b>${fmt(r.sigma,3)}</b> · line spread: <b>${fmt(r.line_spread,3)}</b></p></div><div><span>C</span><p>Confidence: <b>${fmt(r.confidence,1)}/100</b> · sources: <b>${r.source_count||0}</b></p></div></div></div>
    <div class="drawer-section"><div class="section-title">Sportsbook evidence</div><div class="book-row header"><span>Book</span><span>Line</span><span>Over</span><span>Under</span></div>${books}</div>
    <div class="drawer-section"><div class="section-title">Notes</div><div class="notes">${(r.notes||[]).map(n=>`<div class="note">${esc(n)}</div>`).join('')||'<div class="note">No material model warnings.</div>'}<div class="note">Method: ${esc(r.method||'projection comparison')}</div></div></div>
  </div>`;
  $('#drawer').classList.add('open'); $('#drawerBackdrop').classList.remove('hidden');
}
function closeDrawer(){ $('#drawer').classList.remove('open');$('#drawerBackdrop').classList.add('hidden'); }
$('#drawerClose').addEventListener('click',closeDrawer);$('#drawerBackdrop').addEventListener('click',closeDrawer);

async function loadEsports(){
  const game=$('#gameSelect').value; const grid=$('#esportsGrid'); grid.innerHTML='<div class="match-card">Loading fixtures…</div>';
  try{ const d=await api(`/api/esports/upcoming?game=${encodeURIComponent(game)}&limit=24`);
    if(d.mode!=='live'){grid.innerHTML=`<div class="match-card"><div class="match-league">Connector not configured</div><div class="match-name">PandaScore token needed</div><div class="match-meta">${esc(d.message)}</div></div>`;return}
    grid.innerHTML=(d.matches||[]).map(m=>`<div class="match-card"><div class="match-league">${esc(m.league?.name||m.serie?.name||game)}</div><div class="match-name">${esc(m.name||'Upcoming match')}</div><div class="match-meta">${m.begin_at?new Date(m.begin_at).toLocaleString():'TBD'}<br>${esc(m.tournament?.name||'')}<br>Format: ${esc(m.number_of_games||'—')} games</div></div>`).join('')||'<div class="match-card">No upcoming fixtures returned.</div>';
  }catch(e){grid.innerHTML=`<div class="match-card">${esc(e.message)}</div>`}
}

function parseCSV(text){
  const lines=text.split(/\r?\n/).filter(x=>x.trim()); if(lines.length<2)return[];
  const parseLine=(line)=>{const out=[];let cur='',q=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'){if(q&&line[i+1]==='"'){cur+='"';i++}else q=!q}else if(c===','&&!q){out.push(cur);cur=''}else cur+=c}out.push(cur);return out};
  const headers=parseLine(lines[0]).map(x=>x.trim().toLowerCase());
  return lines.slice(1).map(line=>{const vals=parseLine(line);const o={};headers.forEach((h,i)=>o[h]=(vals[i]??'').trim());return {provider:o.provider||'Imported',sport:o.sport||'Unknown',player:o.player||'Unknown',market:o.market||'unknown',line:Number(o.line),projection:o.projection===''?null:Number(o.projection),sigma:o.sigma===''?null:Number(o.sigma),matchup:o.matchup||null,notes:o.notes||null}}).filter(x=>Number.isFinite(x.line));
}

async function analyzeImport(){
  const rows=parseCSV($('#csvText').value); if(!rows.length){toast('No valid CSV rows found.');return}
  try{const d=await api('/api/import/analyze',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({rows})});window.importRows=d.rows||[];renderRows('#importBody',window.importRows);toast(`Analyzed ${window.importRows.length} imported rows.`)}catch(e){toast(e.message)}
}

$('#csvFile').addEventListener('change',async e=>{const f=e.target.files?.[0];if(f)$('#csvText').value=await f.text()});
$('#analyzeImportBtn').addEventListener('click',analyzeImport);$('#loadEsportsBtn').addEventListener('click',loadEsports);$('#refreshBtn').addEventListener('click',loadBoard);$('#sportSelect').addEventListener('change',loadBoard);$('#providerSelect').addEventListener('change',loadBoard);$('#probSelect').addEventListener('change',applyFilters);$('#searchInput').addEventListener('input',applyFilters);
init();
