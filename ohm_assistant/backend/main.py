"""Ohm Assistant — FastAPI application.

Milestone 0: Ingress hello page + Supervisor API entity listing + sensor verify.
Milestone 1: SQLite data layer + CRUD API for config and bills; the ingress page
             becomes a dev console until the SPA lands (M5).
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (registers ORM models on Base)
from .api import bills, config, ha, live, snapshots, stats
from .api.config import get_or_create
from .core import ha as ha_core
from .core import scheduler as sched
from .core import snapshot
from .db import Base, SessionLocal, apply_migrations, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    apply_migrations()
    with SessionLocal() as db:
        get_or_create(db)  # ensure the singleton config row exists
        # Take one snapshot at startup so a period always has a baseline point.
        if ha_core.has_token():
            try:
                snapshot.take_snapshot(db)
            except Exception:  # noqa: BLE001 — startup must not fail on HA hiccups
                pass
    sched.init()
    yield
    sched.shutdown()


app = FastAPI(title="Ohm Assistant", lifespan=lifespan)
app.include_router(config.router)
app.include_router(bills.router)
app.include_router(ha.router)
app.include_router(snapshots.router)
app.include_router(live.router)
app.include_router(stats.router)


@app.get("/api/health")
async def health() -> dict:
    from .core.ha import has_token
    return {"status": "ok", "supervisor_token": has_token()}


DEV_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ohm Assistant</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:46rem;margin:1.5rem auto;padding:0 1rem;color:#111}
 h1{font-size:1.4rem} h3{margin-top:1.8rem;border-bottom:1px solid #eee;padding-bottom:.2rem}
 table{border-collapse:collapse;width:100%;font-size:.88rem}
 td,th{text-align:left;padding:.25rem .4rem;border-bottom:1px solid #eee}
 code{background:#f4f4f5;padding:.05rem .3rem;border-radius:.25rem;font-size:.82rem}
 .ok{color:#059669;font-weight:600} .ko{color:#dc2626;font-weight:600}
 .muted{color:#6b7280} label{font-size:.85rem;margin-right:.6rem}
 input,select{padding:.3rem;border:1px solid #ddd;border-radius:.35rem}
 button{padding:.4rem .8rem;border-radius:.4rem;border:1px solid #ddd;background:#f9fafb;cursor:pointer}
 @media (prefers-color-scheme:dark){
   body{color:#e5e7eb;background:#0b0f19} td,th{border-color:#1f2937} h3{border-color:#1f2937}
   code,input,select{background:#1f2937;color:#e5e7eb;border-color:#374151}
   button{background:#111827;border-color:#374151;color:#e5e7eb}}
</style></head><body>
<h1>⚡ Ohm Assistant <span class="muted" style="font-size:.9rem">— dev console (M1)</span></h1>

<h3>Impostazioni</h3>
<p><label>Andrea <input id="an" size="10"></label>
   <label>Genitori <input id="gn" size="10"></label>
   <label>Canone RAI € <input id="rai" size="6"></label>
   <button onclick="saveCfg()">Salva</button> <span id="cfgmsg" class="muted"></span></p>

<h3>Verifica sensori</h3>
<p><button onclick="verify()">Verifica ora</button> <span id="vsum"></span></p>
<div id="vres"></div>

<h3>Bollette</h3>
<p>
 <label>Tipo <select id="btype"><option value="electric">luce</option><option value="gas">gas</option></select></label>
 <label>dal <input id="bstart" type="date"></label>
 <label>al <input id="bend" type="date"></label>
 <label>q.tà <input id="bq" size="7" placeholder="kWh/Smc"></label>
 <label>€ <input id="bc" size="7"></label>
 <button onclick="addBill()">Aggiungi</button> <span id="bmsg" class="muted"></span>
</p>
<div id="blist">…</div>

<h3>Contatori (snapshot &amp; delta)</h3>
<p><button onclick="snap()">Snapshot ora</button> <span id="smsg" class="muted"></span></p>
<p><label>dal <input id="dfrom" type="date"></label>
   <label>al <input id="dto" type="date"></label>
   <button onclick="delta()">Calcola delta</button>
   <button onclick="importHist()">Importa storico HA</button>
   <span id="imsg" class="muted"></span></p>
<div id="dres"></div>

<h3>Diagnostica</h3>
<p><a href="api/health">health</a> · <a href="api/config">config</a> ·
   <a href="api/bills">bills</a> · <a href="api/ha/verify">verify</a> ·
   <a href="api/snapshots">snapshots</a></p>

<script>
const $=id=>document.getElementById(id);
function loadCfg(){fetch('api/config').then(r=>r.json()).then(c=>{
  $('an').value=c.andrea_name;$('gn').value=c.genitori_name;$('rai').value=c.canone_rai_default;});}
function saveCfg(){$('cfgmsg').textContent='…';
  fetch('api/config',{method:'PUT',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({andrea_name:$('an').value,genitori_name:$('gn').value,
      canone_rai_default:parseFloat($('rai').value)||0})})
  .then(r=>r.json()).then(()=>{$('cfgmsg').textContent='ok';}).catch(e=>$('cfgmsg').textContent='err '+e);}
function verify(){$('vsum').textContent='…';
  fetch('api/ha/verify').then(r=>r.json()).then(d=>{
    $('vsum').innerHTML='<b>'+d.found+'/'+d.total+'</b>'+(d.missing?
      ' · <span class="ko">'+d.missing+' mancanti</span>':' · <span class="ok">ok</span>');
    $('vres').innerHTML='<table>'+d.entities.map(e=>e.found
      ?'<tr><td><code>'+e.entity_id+'</code></td><td><span class="ok">'+e.state+'</span> '+(e.unit||'')+'</td></tr>'
      :'<tr><td><code>'+e.entity_id+'</code></td><td><span class="ko">non trovato</span></td></tr>').join('')+'</table>';
  }).catch(e=>$('vsum').innerHTML='<span class="ko">errore: '+e+'</span>');}
function loadBills(){fetch('api/bills').then(r=>r.json()).then(bs=>{
  $('blist').innerHTML= bs.length? '<table><tr><th>Tipo</th><th>Periodo</th><th>Q.tà</th><th>€</th><th>Andrea</th><th>Genitori</th><th></th></tr>'+
    bs.map(b=>'<tr><td>'+b.type+'</td><td>'+b.period_start+' → '+b.period_end+'</td><td>'+b.billed+
      '</td><td>'+b.cost_total+'</td><td>'+(b.andrea_amount!=null?'€'+b.andrea_amount:'-')+
      '</td><td>'+(b.genitori_amount!=null?'€'+b.genitori_amount:'-')+
      '</td><td><button onclick="computeBill('+b.id+')">Calcola</button> '+
      '<button onclick="delBill('+b.id+')">✕</button></td></tr>').join('')+'</table>'
    : '<p class="muted">nessuna bolletta</p>';});}
function computeBill(id){
  fetch('api/bills/'+id+'/compute',{method:'POST'}).then(r=>r.json()).then(res=>{
    if(res.ok){ loadBills();
      alert('Andrea €'+res.andrea_amount+'  ·  Genitori €'+res.genitori_amount+
        '\\nf_Andrea '+res.f_andrea+(res.warnings&&res.warnings.length?'\\n⚠ '+res.warnings.join('; '):''));
    } else if(res.missing){
      alert('Dati mancanti per il periodo: '+res.missing.join(', ')+
        '\\nUsa \"Importa storico HA\" con le date della bolletta.');
    } else { alert('Errore: '+(res.error||'sconosciuto')); }
  }).catch(e=>alert('err '+e));}
function importHist(){$('imsg').textContent='importo…';
  fetch('api/snapshots/import_history?from_='+$('dfrom').value+'&to='+$('dto').value,{method:'POST'})
  .then(r=>r.json()).then(d=>{ if(d.detail){
      $('imsg').innerHTML='<span class="ok">'+d.keys_imported+'/'+d.keys_total+' sensori importati</span>';
    } else { $('imsg').innerHTML='<span class="ko">'+(d.detail||JSON.stringify(d))+'</span>'; }})
  .catch(e=>$('imsg').innerHTML='<span class="ko">err '+e+'</span>');}
function addBill(){$('bmsg').textContent='…';
  fetch('api/bills',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({type:$('btype').value,period_start:$('bstart').value,period_end:$('bend').value,
      billed:parseFloat($('bq').value),cost_total:parseFloat($('bc').value)})})
  .then(r=>{if(!r.ok)throw r.status;return r.json();})
  .then(()=>{$('bmsg').textContent='ok';loadBills();}).catch(e=>$('bmsg').textContent='err '+e);}
function delBill(id){fetch('api/bills/'+id,{method:'DELETE'}).then(loadBills);}
function snap(){$('smsg').textContent='…';
  fetch('api/snapshots/now',{method:'POST'}).then(r=>r.json())
  .then(d=>{$('smsg').innerHTML='<span class="ok">salvati '+d.stored+'</span>'+
    (d.skipped?' · <span class="ko">saltati '+d.skipped+'</span>':'');})
  .catch(e=>$('smsg').innerHTML='<span class="ko">err '+e+'</span>');}
function delta(){$('dres').textContent='…';
  fetch('api/snapshots/delta?from_='+$('dfrom').value+'&to='+$('dto').value).then(r=>r.json())
  .then(d=>{$('dres').innerHTML='<table><tr><th>Chiave</th><th>Δ periodo</th><th>punti</th></tr>'+
    Object.entries(d.deltas).map(([k,v])=>'<tr><td>'+k+'</td><td>'+
      (v? '<span class=ok>'+v.value+'</span>':'<span class=ko>dati insuff.</span>')+
      '</td><td>'+(v?v.points:'-')+'</td></tr>').join('')+'</table>';})
  .catch(e=>$('dres').innerHTML='<span class="ko">err '+e+'</span>');}
loadCfg();loadBills();verify();
</script>
</body></html>"""


@app.get("/dev", response_class=HTMLResponse)
async def dev_console() -> str:
    return DEV_PAGE


# Serve the built SPA (Milestone 5). Mounted last so /api/* wins.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="spa")
