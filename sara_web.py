"""SARA-OMEGA V3.2.1 browser UI launcher.

Preserves the production bootstrap/fail-safe gates and adds a read-only browser
status dashboard at /app and /ui. No secret material is rendered client-side.
"""
from __future__ import annotations

import logging
import os

import uvicorn
from fastapi.responses import HTMLResponse

from sara_production_bootstrap import (
    configure_production_defaults,
    failed_evidence,
    register_acceptance_routes,
    run_preflight,
)

logger = logging.getLogger("sara.web")

UI_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="color-scheme" content="dark" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'" />
  <title>SARA-OMEGA V3.2.1</title>
  <style>
    :root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#090b12;color:#f5f7fb}
    *{box-sizing:border-box} body{margin:0;min-height:100vh;background:radial-gradient(circle at 85% 10%,rgba(119,74,255,.22),transparent 32%),linear-gradient(180deg,#0d1019,#080a10 62%)}
    .shell{width:min(980px,92vw);margin:0 auto;padding:28px 0 48px}.top{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:28px}
    .brand{display:flex;align-items:center;gap:14px}.mark{width:48px;height:48px;border-radius:16px;background:linear-gradient(145deg,#8e67ff,#4f2ed4);display:grid;place-items:center;font-weight:900;box-shadow:0 16px 44px rgba(97,62,216,.35)}
    h1{font-size:clamp(28px,5vw,46px);margin:0;letter-spacing:-.03em}.sub{color:#aab0c2;margin-top:5px;font-size:14px}.pill{border:1px solid #2f3446;background:#151925;padding:9px 12px;border-radius:999px;color:#cdd2df;font-size:13px}
    .hero{border:1px solid #24293a;border-radius:26px;padding:28px;background:rgba(17,20,31,.88);box-shadow:0 24px 80px rgba(0,0,0,.25);margin-bottom:18px}.heroTop{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap}
    .eyebrow{color:#9277ff;text-transform:uppercase;letter-spacing:.16em;font-size:12px;font-weight:800}.status{font-size:clamp(34px,6vw,58px);font-weight:820;letter-spacing:-.04em;margin:8px 0 8px}.ok{color:#67e8a9}.warn{color:#fbbf65}.bad{color:#fb7185}.muted{color:#a7aec0;line-height:1.6;max-width:650px}
    .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:24px}.card{padding:17px;border-radius:18px;background:#111520;border:1px solid #24293a}.label{font-size:12px;color:#838ba0;margin-bottom:9px;text-transform:uppercase;letter-spacing:.08em}.value{font-size:17px;font-weight:700;word-break:break-word}
    .wide{grid-column:span 2}.section{display:grid;grid-template-columns:1fr 1fr;gap:14px}.panel{border:1px solid #24293a;background:#10141e;border-radius:22px;padding:20px}.panel h2{margin:0 0 14px;font-size:18px}.row{display:flex;justify-content:space-between;gap:15px;padding:11px 0;border-bottom:1px solid #222635}.row:last-child{border-bottom:0}.row span:first-child{color:#9299ad}.row strong{text-align:right}
    .actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}.btn{appearance:none;text-decoration:none;color:#f5f7fb;background:#181d2b;border:1px solid #30364a;padding:11px 14px;border-radius:14px;font-weight:700}.btn.primary{background:#7357ed;border-color:#8068ef}.foot{color:#737b90;text-align:center;font-size:12px;margin-top:24px}
    @media(max-width:760px){.grid{grid-template-columns:1fr 1fr}.section{grid-template-columns:1fr}.top{align-items:flex-start}.pill{display:none}} @media(max-width:420px){.grid{grid-template-columns:1fr}.wide{grid-column:span 1}}
  </style>
</head>
<body>
<main class="shell">
  <div class="top">
    <div class="brand"><div class="mark">SΩ</div><div><h1>SARA-OMEGA</h1><div class="sub">Governed runtime • Railway production</div></div></div>
    <div class="pill">V3.2.1</div>
  </div>

  <section class="hero">
    <div class="heroTop">
      <div><div class="eyebrow">Production state</div><div id="headline" class="status">Checking…</div><div id="summary" class="muted">Reading live production acceptance evidence from this deployment.</div></div>
    </div>
    <div class="grid">
      <div class="card"><div class="label">Release</div><div id="version" class="value">—</div></div>
      <div class="card"><div class="label">Platform</div><div id="platform" class="value">—</div></div>
      <div class="card wide"><div class="label">Hardening profile</div><div id="hardening" class="value">—</div></div>
      <div class="card"><div class="label">Readiness</div><div id="ready" class="value">—</div></div>
      <div class="card"><div class="label">Persistence</div><div id="persistence" class="value">—</div></div>
      <div class="card"><div class="label">Chain integrity</div><div id="chain" class="value">—</div></div>
      <div class="card"><div class="label">Dedicated storage</div><div id="mount" class="value">—</div></div>
    </div>
    <div class="actions">
      <a class="btn primary" href="/docs">Open API Console</a>
      <a class="btn" href="/health/production-acceptance">Raw Acceptance Evidence</a>
      <a class="btn" href="/health">System Health</a>
    </div>
  </section>

  <section class="section">
    <div class="panel"><h2>Trust & fail-safe</h2>
      <div class="row"><span>Bootstrap</span><strong id="bootstrap">—</strong></div>
      <div class="row"><span>Fail-safe configured</span><strong id="failsafe">—</strong></div>
      <div class="row"><span>Checkpoint self-test</span><strong id="checkpoint">—</strong></div>
      <div class="row"><span>Cross-boot persistence</span><strong id="crossboot">—</strong></div>
    </div>
    <div class="panel"><h2>Runtime</h2>
      <div class="row"><span>Public liveness</span><strong id="live">—</strong></div>
      <div class="row"><span>Base provenance</span><strong id="base">—</strong></div>
      <div class="row"><span>Owner authority configured</span><strong id="owner">—</strong></div>
      <div class="row"><span>Last refresh</span><strong id="refreshed">—</strong></div>
    </div>
  </section>
  <div class="foot">SARA-OMEGA V3.2.1 • Read-only operational dashboard • No secrets are displayed</div>
</main>
<script>
const text=(id,v)=>document.getElementById(id).textContent=v;
const yn=v=>v===true?'PASS':v===false?'FAIL':'—';
async function load(){
  try{
    const [rootR,healthR,liveR,readyR,accR]=await Promise.all([fetch('/'),fetch('/health'),fetch('/health/live'),fetch('/health/ready'),fetch('/health/production-acceptance')]);
    const root=await rootR.json(); const health=await healthR.json(); const live=await liveR.json(); const acc=await accR.json();
    const accepted=acc.production_accepted===true; const ready=readyR.ok;
    const h=document.getElementById('headline'); h.textContent=accepted?'Production Accepted':(ready?'Online — Acceptance Pending':'Fail-Closed'); h.className='status '+(accepted?'ok':ready?'warn':'bad');
    text('summary',accepted?'All published V3.2.1 production acceptance predicates are satisfied.':'The service is online, but one or more production trust predicates are not yet satisfied.');
    text('version',root.version||acc.release_version||'—'); text('platform',root.platform||health.platform||'—'); text('hardening',root.hardening_profile||acc.hardening_profile||'—');
    text('ready',ready?'PASS':'FAIL'); text('persistence',acc.persistence_status||'—'); text('chain',yn(acc.chain_valid)); text('mount',yn(acc.root_on_dedicated_mount));
    text('bootstrap',yn(acc.bootstrap_ready)); text('failsafe',yn(acc.failsafe_configured)); text('checkpoint',yn(acc.checkpoint_self_test)); text('crossboot',yn(acc.persistence_observed_across_boots));
    text('live',live.alive===true?'PASS':'FAIL'); text('base',root.base_runtime_version||health.base_runtime_version||'—'); text('owner',yn(acc.owner_token_configured)); text('refreshed',new Date().toLocaleTimeString());
  }catch(e){const h=document.getElementById('headline'); h.textContent='Status unavailable'; h.className='status bad'; text('summary','The dashboard could not read one or more local health endpoints.'); text('refreshed',new Date().toLocaleTimeString());}
}
load(); setInterval(load,15000);
</script>
</body>
</html>'''


def register_ui_routes(app) -> None:
    @app.get("/app", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    def sara_ui() -> HTMLResponse:
        return HTMLResponse(UI_HTML, headers={"Cache-Control": "no-store"})


def run() -> None:
    configure_production_defaults()
    try:
        evidence = run_preflight()
        logger.info("SARA browser bootstrap PASS: %s", evidence.get("persistence_status"))
    except Exception as exc:
        evidence = failed_evidence(exc)
        logger.error("SARA browser bootstrap BLOCKED: %s", evidence.get("failure_reason"))

    import main as main_module

    if not evidence.get("bootstrap_ready"):
        main_module.FAILSAFE.required = True
        main_module.FAILSAFE.controller = None
        main_module.FAILSAFE.init_error = "production_bootstrap_gate_failed"

    register_acceptance_routes(main_module, evidence)
    register_ui_routes(main_module.app)
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(main_module.app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
