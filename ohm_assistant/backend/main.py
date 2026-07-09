"""Ohm Assistant — FastAPI application.

Milestone 0: Ingress hello page + Supervisor API entity listing + a "verify
sensors" panel that checks the real meter/PV entities the app will rely on.

The Supervisor proxy needs no user token: ``SUPERVISOR_TOKEN`` is injected by
Home Assistant because the add-on declares ``homeassistant_api: true``.
"""
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .entities import all_default_ids

SUPERVISOR = "http://supervisor/core/api"
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

app = FastAPI(title="Ohm Assistant")


def _headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "supervisor_token": bool(TOKEN)}


@app.get("/api/ha/entities")
async def ha_entities(domain: str = "sensor") -> dict:
    """List HA entities of a domain via the Supervisor proxy."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{SUPERVISOR}/states", headers=_headers())
    resp.raise_for_status()
    states = resp.json()
    entities = [
        {"entity_id": s["entity_id"], "state": s["state"],
         "name": s["attributes"].get("friendly_name", s["entity_id"])}
        for s in states
        if s["entity_id"].startswith(f"{domain}.")
    ]
    return {"domain": domain, "count": len(entities), "entities": entities}


@app.get("/api/ha/verify")
async def ha_verify() -> dict:
    """Fetch the current state of every default entity (SPEC 3).

    Returns each id with its state + unit, or found=false when HA doesn't know
    it (typo, renamed, or not yet available). Drives the M0 checklist.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{SUPERVISOR}/states", headers=_headers())
    resp.raise_for_status()
    by_id = {s["entity_id"]: s for s in resp.json()}

    out = []
    for eid in all_default_ids():
        s = by_id.get(eid)
        if s is None:
            out.append({"entity_id": eid, "found": False})
        else:
            out.append({
                "entity_id": eid,
                "found": True,
                "state": s["state"],
                "unit": s["attributes"].get("unit_of_measurement", ""),
                "name": s["attributes"].get("friendly_name", eid),
            })
    found = sum(1 for x in out if x["found"])
    return {"total": len(out), "found": found, "missing": len(out) - found,
            "entities": out}


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ohm Assistant</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:44rem;margin:1.5rem auto;padding:0 1rem;
   color:#111}
 h1{font-size:1.4rem} h3{margin-top:1.6rem}
 table{border-collapse:collapse;width:100%;font-size:.9rem}
 td,th{text-align:left;padding:.25rem .4rem;border-bottom:1px solid #eee}
 code{background:#f4f4f5;padding:.05rem .3rem;border-radius:.25rem;font-size:.82rem}
 .ok{color:#059669;font-weight:600} .ko{color:#dc2626;font-weight:600}
 .muted{color:#6b7280} button{padding:.4rem .8rem;border-radius:.4rem;border:1px solid #ddd;
   background:#f9fafb;cursor:pointer}
 @media (prefers-color-scheme:dark){
   body{color:#e5e7eb;background:#0b0f19} td,th{border-color:#1f2937}
   code{background:#1f2937} button{background:#111827;border-color:#374151;color:#e5e7eb}}
</style></head><body>
<h1>⚡ Ohm Assistant</h1>
<p class="muted">Add-on avviato — Milestone 0 (scaffold). Specifica in <code>SPEC.md</code>.</p>

<h3>Verifica sensori</h3>
<p class="muted">Controlla che Home Assistant esponga gli entity_id su cui si baserà il
calcolo. In rosso quelli non trovati (da correggere nel Setup, in arrivo con M1).</p>
<p><button onclick="verify()">Verifica ora</button> <span id="summary"></span></p>
<div id="result"></div>

<h3>Diagnostica</h3>
<p><a href="api/health">health</a> · <a href="api/ha/verify">verify (JSON)</a> ·
<a href="api/ha/entities?domain=sensor">tutti i sensor</a></p>

<script>
function verify(){
  document.getElementById('summary').textContent='…';
  fetch('api/ha/verify').then(r=>r.json()).then(d=>{
    document.getElementById('summary').innerHTML =
      '<b>'+d.found+'/'+d.total+'</b> trovati'+
      (d.missing? ' · <span class="ko">'+d.missing+' mancanti</span>':' · <span class="ok">tutti ok</span>');
    document.getElementById('result').innerHTML =
      '<table><tr><th>Entity</th><th>Stato</th></tr>'+
      d.entities.map(e=> e.found
        ? '<tr><td><code>'+e.entity_id+'</code></td><td><span class="ok">'+
          e.state+'</span> '+(e.unit||'')+'</td></tr>'
        : '<tr><td><code>'+e.entity_id+'</code></td><td><span class="ko">non trovato</span></td></tr>'
      ).join('')+'</table>';
  }).catch(e=>{document.getElementById('summary').innerHTML=
    '<span class="ko">errore: '+e+'</span>';});
}
verify();
</script>
</body></html>"""
