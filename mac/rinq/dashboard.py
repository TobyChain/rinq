"""Self-contained web dashboard for the ring status.

Served by the Mac daemon so you can check quota from any browser (iPhone,
iPad, another machine) with no app install and no code signing. Pure static
HTML/JS/CSS; it polls /status and /sessions.
"""

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#000000">
<title>Rinq</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body { margin:0; background:#000; color:#fff; font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif; }
  .wrap { max-width: 520px; margin: 0 auto; padding: max(env(safe-area-inset-top),20px) 18px 40px; }
  h1 { font-size: 34px; font-weight: 800; letter-spacing: -0.02em; margin: 4px 0 16px; }
  .agents { display:none; gap:8px; flex-direction:column; margin: 0 0 18px; padding: 12px;
            background: rgba(255,255,255,.06); border-radius: 12px; }
  .agents.on { display:flex; }
  .agents .counts { display:flex; gap:10px; flex:none; font-size:12px; font-weight:700;
                    font-variant-numeric: tabular-nums; }
  .agents .counts span { display:flex; gap:4px; align-items:center; }
  .agents .dot { width:7px; height:7px; border-radius:50%; }
  .agents .chips { display:flex; flex-direction:column; gap:6px; max-height:380px; overflow-y:auto; width:100%; }
  .chip { flex:none; display:flex; flex-direction:column; gap:5px; padding:9px; border-radius:8px;
          background: rgba(255,255,255,.08); font-size:11px; min-width:0; }
  .chip .heading { display:flex; gap:6px; align-items:center; }
  .chip .heading small { margin-left:auto; }
  .chip .summary, .chip .meta { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .chip .meta { color:#9aa0a6; font-size:10px; }
  .chip b { font-size:9px; letter-spacing:.04em; color:#9aa0a6; }
  .chip small { color:#9aa0a6; font-size:9px; }
  .bar { display:flex; align-items:center; gap:12px; margin: 0 0 14px; }
  .bar .info { flex:1; min-width:0; }
  .bar .label { font-size:16px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bar .val { font-size:13px; font-weight:700; font-variant-numeric: tabular-nums; margin-top:2px; }
  .bar .sub { font-size:12px; color:#9aa0a6; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .mini { flex:none; position:relative; width:48px; height:48px; }
  .mini svg { transform: rotate(-90deg); }
  .mini .pct { position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
               font-size:10px; font-weight:800; font-variant-numeric: tabular-nums; }
  .updated { text-align:center; color:#777; font-size:12px; margin-top:8px; }
  .err { text-align:center; color:#ff6b6b; font-size:13px; margin-top:8px; display:none; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Rinq</h1>
  <div class="agents" id="agents">
    <div class="counts" id="counts"></div>
    <div class="chips" id="chips"></div>
  </div>
  <div id="bars"></div>
  <div class="updated" id="updated"></div>
  <div class="err" id="err">couldn't reach this Mac — check the network</div>
</div>
<script>
const COLORS = { blue:'#0a84ff', indigo:'#5e5ce6', green:'#30d158', orange:'#ff9f0a', red:'#ff453a', purple:'#bf5af2', teal:'#64d2ff' };
const STATE_COLORS = { running:'#0a84ff', subagents_running:'#bf5af2', waiting:'#ff9f0a', failed:'#ff453a', completed:'#30d158', idle:'#8e8e93' };
const STATE_LABELS = { running:'running', subagents_running:'subagents running', waiting:'waiting', idle:'idling' };
const APP_SHORT = { claude_code:'CC', codex:'CX', traex:'TR', omp:'OMP', pi:'PI' };
function col(a){ return COLORS[a] || COLORS.blue; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function sym(r){ return r.currency==='USD' ? '$' : '¥'; }
function amount(r){ return (r.remaining!=null) ? (sym(r)+Number(r.remaining).toFixed(2)) : null; }
function resetText(r){
  if(r.resetsAt){
    const s=r.resetsAt - Math.floor(Date.now()/1000);
    if(s<=0) return 'quota window ended';
    const m=Math.floor(s/60);
    if(m>=1440) return 'resets in '+Math.floor(m/1440)+'d';
    if(m>=60) return 'resets in '+Math.floor(m/60)+'h '+(m%60)+'m';
    return 'resets in '+m+'m';
  }
  return '';
}
function formatValue(value, unit){
  const n = Number(value);
  const text = Number.isInteger(n) ? String(n) : n.toFixed(2);
  if(unit==='USD') return '$'+text;
  if(unit==='CNY') return '¥'+text;
  if(unit==='percent') return text+'%';
  return text;
}
// The ring carries the percentage; the row text shows only used / total.
function rowValue(r){
  if(r.status==='quota_unavailable') return 'Unavailable';
  if(r.status==='quota_unsupported') return 'Not supported';
  if(r.status==='not_connected') return 'Not connected';
  if(r.usedValue!=null && r.totalValue!=null){
    return formatValue(r.usedValue,r.valueUnit)+' / '+formatValue(r.totalValue,r.valueUnit);
  }
  return amount(r) || '--';
}
function miniRing(r){
  const p = r.usedPercent;
  const hasPct = (p!=null);
  const c = (!hasPct && !amount(r)) ? '#888' : col(r.accent);
  const R=19, W=5, cLen=2*Math.PI*R, dash=cLen*Math.max(0,Math.min(100,hasPct?p:0))/100;
  return `<div class="mini">
    <svg width="48" height="48" viewBox="0 0 48 48">
      <circle cx="24" cy="24" r="${R}" fill="none" stroke="${c}" stroke-opacity="0.18" stroke-width="${W}"/>
      <circle cx="24" cy="24" r="${R}" fill="none" stroke="${c}" stroke-width="${W}"
        stroke-linecap="round" stroke-dasharray="${dash} ${cLen}"/>
    </svg>
    <span class="pct" style="color:${c}">${hasPct?p:'–'}</span>
  </div>`;
}
function bars(rings){
  document.getElementById('bars').innerHTML = rings.map(r=>{
    const hasPct = (r.usedPercent!=null);
    const dead = !hasPct && !amount(r);
    const c = dead ? '#888' : col(r.accent);
    const sub = resetText(r) || r.statusDetail || (dead ? 'no data — add a key' : '');
    return `<div class="bar">
      <div class="info">
        <div class="label">${esc(r.label)}</div>
        <div class="val" style="color:${c}">${esc(rowValue(r))}</div>
        <div class="sub">${esc(sub)}</div>
      </div>
      ${miniRing(r)}
    </div>`;
  }).join('');
}
function agents(d){
  const box = document.getElementById('agents');
  const sessions = ((d && d.sessions) || []).filter(s=>s.isOpen===true);
  if(!sessions.length){ box.classList.remove('on'); return; }
  const counts = d.counts || {};
  const parts = [];
  if(counts.running>0) parts.push(`<span><i class="dot" style="background:${STATE_COLORS.running}"></i>${counts.running} run</span>`);
  if(counts.subagentsRunning>0) parts.push(`<span><i class="dot" style="background:${STATE_COLORS.subagents_running}"></i>${counts.subagentsRunning} sub</span>`);
  if(counts.waiting>0) parts.push(`<span><i class="dot" style="background:${STATE_COLORS.waiting}"></i>${counts.waiting} wait</span>`);
  if(counts.idle>0) parts.push(`<span><i class="dot" style="background:${STATE_COLORS.idle}"></i>${counts.idle} idle</span>`);
  document.getElementById('counts').innerHTML = parts.join('');
  document.getElementById('chips').innerHTML = sessions.slice(0,12).map(s=>{
    const c = STATE_COLORS[s.state] || STATE_COLORS.idle;
    const tip = esc((s.summary||'') + ' · ' + (STATE_LABELS[s.state] || s.state));
    const meta = [s.model, s.cwd, s.updatedAt ? new Date(s.updatedAt*1000).toLocaleTimeString() : null].filter(Boolean).join(' · ');
    return `<div class="chip" title="${tip}"><div class="heading"><i class="dot" style="background:${c}"></i>`+
           `<b>${esc(s.app||APP_SHORT[s.adapter]||'Agent')}</b>${esc(s.project||'')} <small>${esc(STATE_LABELS[s.state]||s.state)}</small></div>`+
           `<div class="summary">${esc(s.summary||'')}</div><div class="meta" title="${esc(meta)}">${esc(meta)}</div></div>`;
  }).join('');
  box.classList.add('on');
}
async function load(){
  try{
    const sr = await fetch('status', {cache:'no-store'}).then(r=>r.ok ? r.json() : null).catch(()=>null);
    document.getElementById('err').style.display = sr ? 'none' : 'block';
    if(sr){
      bars(sr.rings||[]);
      const t=sr.updatedAt? new Date(sr.updatedAt*1000) : null;
      document.getElementById('updated').textContent = t? ('updated '+t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})) : '';
    }
  }catch(e){ document.getElementById('err').style.display='block'; }
  finally { setTimeout(load, 15000); }
}
async function loadSessions(){
  try {
    const snapshot = await fetch('sessions', {cache:'no-store'}).then(r=>r.ok ? r.json() : null);
    agents(snapshot);
  } catch(e) { agents(null); }
  finally { setTimeout(loadSessions, 2000); }
}
load();
loadSessions();
</script>
</body>
</html>
"""
