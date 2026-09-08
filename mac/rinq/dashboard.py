"""Self-contained web dashboard for the ring status.

Served by the Mac daemon so you can check quota from any browser (iPhone,
iPad, another machine) with no app install and no code signing. Pure static
HTML/JS/CSS; it polls /status every 60s.
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
  h1 { font-size: 34px; font-weight: 800; letter-spacing: -0.02em; margin: 4px 0 18px; }
  .rings { position: relative; width: 260px; height: 260px; margin: 6px auto 22px; }
  .rings svg { transform: rotate(-90deg); }
  .rings .center { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
  .rings .center b { font-size: 30px; font-weight: 800; }
  .rings .center span { font-size: 12px; color:#9aa0a6; margin-top:2px; }
  .bar { margin: 0 0 18px; }
  .bar .top { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px; }
  .bar .label { font-size: 16px; font-weight: 600; }
  .bar .val { font-size: 16px; font-weight: 800; font-variant-numeric: tabular-nums; }
  .bar .track { height: 10px; border-radius: 6px; background: rgba(255,255,255,.08); overflow:hidden; }
  .bar .fill { height:100%; border-radius:6px; transition: width .6s ease; }
  .bar .sub { font-size: 12px; color:#9aa0a6; margin-top:5px; }
  .updated { text-align:center; color:#777; font-size:12px; margin-top:8px; }
  .err { text-align:center; color:#ff6b6b; font-size:13px; margin-top:8px; display:none; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Rinq</h1>
  <div class="rings">
    <svg width="260" height="260" viewBox="0 0 260 260" id="rings"></svg>
    <div class="center"><b id="head">–</b><span id="headsub">rings</span></div>
  </div>
  <div id="bars"></div>
  <div class="updated" id="updated"></div>
  <div class="err" id="err">couldn't reach this Mac — check the network</div>
</div>
<script>
const COLORS = { blue:'#0a84ff', indigo:'#5e5ce6', green:'#30d158', orange:'#ff9f0a', red:'#ff453a', purple:'#bf5af2', teal:'#64d2ff' };
function col(a){ return COLORS[a] || COLORS.blue; }
function pctOf(r){ return r.usedPercent; }
function sym(r){ return r.currency==='USD' ? '$' : '¥'; }
function amount(r){ return (r.remaining!=null) ? (sym(r)+Number(r.remaining).toFixed(2)) : null; }
// Unknown only when neither a percentage nor an absolute amount is available.
function unknown(r){ return pctOf(r)==null && !amount(r); }
function arc(radius, pct, color, width){
  const c=2*Math.PI*radius, dash=c*Math.max(0,Math.min(100,pct||0))/100;
  return `<circle cx="130" cy="130" r="${radius}" fill="none" stroke="${color}" stroke-opacity="0.18" stroke-width="${width}"/>
          <circle cx="130" cy="130" r="${radius}" fill="none" stroke="${color}" stroke-width="${width}"
            stroke-linecap="round" stroke-dasharray="${dash} ${c}"/>`;
}
function resetText(r){
  if(r.resetsAt){
    const s=r.resetsAt - Math.floor(Date.now()/1000);
    if(s<=0) return 'quota window ended';
    const m=Math.floor(s/60);
    if(m>=1440) return 'resets in '+Math.floor(m/1440)+'d';
    if(m>=60) return 'resets in '+Math.floor(m/60)+'h '+(m%60)+'m';
    return 'resets in '+m+'m';
  }
  return (r.usedPercent??0)+'%';
}
function formatValue(value, unit){
  const n = Number(value);
  const text = Number.isInteger(n) ? String(n) : n.toFixed(2);
  if(unit==='USD') return '$'+text;
  if(unit==='CNY') return '¥'+text;
  if(unit==='percent') return text+'%';
  return text;
}
function usageText(r){
  if(r.usedValue!=null && r.totalValue!=null)
    return formatValue(r.usedValue,r.valueUnit)+' / '+formatValue(r.totalValue,r.valueUnit);
  return (r.usedPercent??0)+'% / 100%';
}
async function load(){
  try{
    const res = await fetch('status', {cache:'no-store'});
    const d = await res.json();
    document.getElementById('err').style.display='none';
    draw(d.rings||[]);
    bars(d.rings||[]);
    const t=d.updatedAt? new Date(d.updatedAt*1000) : null;
    document.getElementById('updated').textContent = t? ('updated '+t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})) : '';
  }catch(e){ document.getElementById('err').style.display='block'; }
}
function draw(rings){
  const top = rings.slice(0,3);
  const W=13, gap=12, base=118;
  document.getElementById('rings').innerHTML = top.map((r,i)=>{
    const rad = base - i*(W+gap);
    const p = pctOf(r);
    return arc(rad, (p==null?0:p), (p==null&&!amount(r))?'#888':col(r.accent), W);
  }).join('');
  document.getElementById('head').textContent = top.length? top.length : '–';
}
function bars(rings){
  document.getElementById('bars').innerHTML = rings.map(r=>{
    const p = pctOf(r);
    const hasPct = (p!=null);
    const amt = amount(r);
    const v = hasPct ? usageText(r) : (amt || '--');
    const dead = !hasPct && !amt;
    const c = dead ? '#888' : col(r.accent);
    return `<div class="bar">
      <div class="top"><span class="label">${r.label}</span><span class="val" style="color:${c}">${v}</span></div>
      <div class="track"><div class="fill" style="width:${hasPct?p:0}%;background:${c}"></div></div>
      <div class="sub">${dead?'no data — add a key':resetText(r)}</div>
    </div>`;
  }).join('');
}
load();
setInterval(load, 60000);
</script>
</body>
</html>
"""
