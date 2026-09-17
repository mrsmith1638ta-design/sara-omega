"""Owner-only browser console for the governed SARA Piper voice.

The browser never receives or persists OWNER_TOKEN after login. A successful
owner-token check creates a short-lived opaque session cookie; server-side
session state is bound to a digest of the current owner token so token rotation
invalidates existing sessions fail-closed.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from types import SimpleNamespace
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from sara_unified.api.schemas import VoiceSynthesisRequest
from sara_unified.voice.profile import SARA_VOICE_PROFILE

VOICE_CONSOLE_COOKIE = "sara_voice_owner_session"
VOICE_CONSOLE_SESSION_TTL_SECONDS = 900

# key: sha256(opaque browser session id)
# value: (monotonic expiration, sha256(owner token at login))
_VOICE_CONSOLE_SESSIONS: dict[str, tuple[float, str]] = {}
_VOICE_CONSOLE_SESSION_LOCK = threading.Lock()


class VoiceConsoleLogin(BaseModel):
    owner_token: str = Field(min_length=1, max_length=4096)


def _main_module():
    # Lazy import avoids changing the existing application bootstrap/import order.
    import main as main_module

    return main_module


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _security_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "connect-src 'self'; media-src 'self' blob:; img-src 'self' data:; "
            "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        ),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }


def _json(content: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=content, status_code=status_code, headers=_security_headers())


def _origin_allowed(request: Request) -> bool:
    """Allow non-browser/no-Origin calls or the exact HTTPS host serving SARA."""
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return True
    host = request.headers.get("host", "").strip()
    if not host:
        return False
    return secrets.compare_digest(origin, f"https://{host}")


def _reject_foreign_origin(request: Request) -> JSONResponse | None:
    if _origin_allowed(request):
        return None
    return _json({"detail": "Forbidden"}, status_code=403)


def _prune_expired(now: float) -> None:
    with _VOICE_CONSOLE_SESSION_LOCK:
        expired = [key for key, (expires_at, _) in _VOICE_CONSOLE_SESSIONS.items() if expires_at <= now]
        for key in expired:
            _VOICE_CONSOLE_SESSIONS.pop(key, None)


def _remove_session(session_id: str) -> None:
    if not session_id:
        return
    with _VOICE_CONSOLE_SESSION_LOCK:
        _VOICE_CONSOLE_SESSIONS.pop(_digest(session_id), None)


def _session_valid(request: Request, *, owner_token: str, kill_switch: bool) -> bool:
    if kill_switch or not owner_token:
        return False
    session_id = request.cookies.get(VOICE_CONSOLE_COOKIE, "")
    if not session_id:
        return False

    now = time.monotonic()
    _prune_expired(now)
    session_key = _digest(session_id)
    with _VOICE_CONSOLE_SESSION_LOCK:
        record = _VOICE_CONSOLE_SESSIONS.get(session_key)
    if record is None:
        return False

    expires_at, bound_owner_digest = record
    if expires_at <= now:
        _remove_session(session_id)
        return False
    current_owner_digest = _digest(owner_token)
    if not secrets.compare_digest(bound_owner_digest, current_owner_digest):
        _remove_session(session_id)
        return False
    return True


def _new_session(owner_token: str) -> str:
    now = time.monotonic()
    _prune_expired(now)
    session_id = secrets.token_urlsafe(32)
    with _VOICE_CONSOLE_SESSION_LOCK:
        _VOICE_CONSOLE_SESSIONS[_digest(session_id)] = (
            now + VOICE_CONSOLE_SESSION_TTL_SECONDS,
            _digest(owner_token),
        )
    return session_id


def _set_session_cookie(response: JSONResponse, session_id: str) -> None:
    response.set_cookie(
        key=VOICE_CONSOLE_COOKIE,
        value=session_id,
        max_age=VOICE_CONSOLE_SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/voice-console",
    )


def _clear_session_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=VOICE_CONSOLE_COOKIE,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/voice-console",
    )


VOICE_CONSOLE_HTML = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <meta name="color-scheme" content="dark" />
  <title>SARA OMEGA Voice Console</title>
  <style>
    :root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#080a10;color:#f5f7fb}}
    *{{box-sizing:border-box}} body{{margin:0;min-height:100vh;background:radial-gradient(circle at 85% 5%,rgba(119,74,255,.24),transparent 30%),linear-gradient(180deg,#0d1019,#080a10 66%)}}
    main{{width:min(760px,92vw);margin:0 auto;padding:34px 0 48px}} .brand{{display:flex;align-items:center;gap:14px;margin-bottom:24px}} .mark{{width:48px;height:48px;border-radius:16px;background:linear-gradient(145deg,#8e67ff,#4f2ed4);display:grid;place-items:center;font-weight:900}}
    h1{{font-size:clamp(28px,6vw,44px);margin:0;letter-spacing:-.035em}} .sub{{color:#aab0c2;margin-top:5px}} .panel{{border:1px solid #252a3b;border-radius:24px;background:rgba(16,20,30,.92);padding:24px;box-shadow:0 24px 80px rgba(0,0,0,.24)}}
    .profile{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 22px}} .profile div{{background:#121724;border:1px solid #252b3d;border-radius:16px;padding:14px}} .label{{display:block;color:#858da3;text-transform:uppercase;letter-spacing:.08em;font-size:11px;margin-bottom:6px}} strong{{word-break:break-word}}
    label{{display:block;font-weight:750;margin:0 0 8px}} input,textarea{{width:100%;border:1px solid #343b51;background:#0b0f18;color:#f7f8fb;border-radius:14px;padding:13px 14px;font:inherit;outline:none}} input:focus,textarea:focus{{border-color:#8e72ff;box-shadow:0 0 0 3px rgba(142,114,255,.15)}} textarea{{min-height:180px;resize:vertical;line-height:1.5}}
    .row{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;flex-wrap:wrap}} .buttons{{display:flex;gap:10px;flex-wrap:wrap}} button{{appearance:none;border:1px solid #343b51;background:#181e2d;color:#f7f8fb;border-radius:13px;padding:11px 16px;font:inherit;font-weight:760;cursor:pointer}} button.primary{{background:#7357ed;border-color:#8068ef}} button:disabled{{opacity:.5;cursor:not-allowed}}
    .muted{{color:#99a1b5;font-size:13px;line-height:1.55}} .status{{margin-top:14px;min-height:22px;color:#b9c1d3}} .error{{color:#fb8b9d}} .ok{{color:#72e7ac}} audio{{width:100%;margin-top:14px}} .hidden{{display:none!important}} .foot{{color:#727b91;text-align:center;font-size:12px;margin-top:20px}}
    @media(max-width:560px){{.profile{{grid-template-columns:1fr}} .panel{{padding:18px}}}}
  </style>
</head>
<body>
<main>
  <div class="brand"><div class="mark" aria-hidden="true">SΩ</div><div><h1>SARA OMEGA Voice Console</h1><div class="sub">Governed owner access • Production Piper voice</div></div></div>
  <section class="panel">
    <div class="profile" aria-label="Fixed voice profile">
      <div><span class="label">Voice profile</span><strong>{SARA_VOICE_PROFILE.profile_id}</strong></div>
      <div><span class="label">Pinned model</span><strong>{SARA_VOICE_PROFILE.model_id}</strong></div>
    </div>

    <div id="loginPanel">
      <label for="ownerToken">Owner credential</label>
      <input id="ownerToken" type="password" autocomplete="current-password" spellcheck="false" />
      <div class="row"><span class="muted">Used once to establish a 15-minute secure owner session. It is not stored in browser storage.</span><button id="loginButton" class="primary" type="button">Sign in</button></div>
    </div>

    <div id="consolePanel" class="hidden">
      <label for="speechText">What should SARA say?</label>
      <textarea id="speechText" maxlength="4000" placeholder="Type the words you want SARA to speak."></textarea>
      <div class="row"><span id="count" class="muted">0 / 4000</span><div class="buttons"><button id="stopButton" type="button">Stop</button><button id="speakButton" class="primary" type="button">Speak</button><button id="logoutButton" type="button">Sign out</button></div></div>
      <audio id="player" controls preload="none"></audio>
    </div>
    <div id="status" class="status" role="status" aria-live="polite">Checking owner session…</div>
  </section>
  <div class="foot">Fixed SARA British professional voice • No model selection • Private Piper service remains internal</div>
</main>
<script>
const loginPanel=document.getElementById('loginPanel');
const consolePanel=document.getElementById('consolePanel');
const tokenInput=document.getElementById('ownerToken');
const textInput=document.getElementById('speechText');
const count=document.getElementById('count');
const statusEl=document.getElementById('status');
const player=document.getElementById('player');
let controller=null; let audioUrl=null;
function status(message,kind=''){{statusEl.textContent=message;statusEl.className='status '+kind;}}
function showAuthenticated(authenticated){{loginPanel.classList.toggle('hidden',authenticated);consolePanel.classList.toggle('hidden',!authenticated);if(authenticated){{tokenInput.value='';textInput.focus();}}}}
function releaseAudio(){{if(audioUrl){{URL.revokeObjectURL(audioUrl);audioUrl=null;}} player.removeAttribute('src');player.load();}}
async function sessionState(){{try{{const r=await fetch('/voice-console/session',{{cache:'no-store',credentials:'same-origin'}});const data=await r.json();showAuthenticated(data.authenticated===true);status(data.authenticated?'Owner session active.':'Sign in to use SARA voice.',data.authenticated?'ok':'');}}catch(e){{showAuthenticated(false);status('Owner session unavailable.','error');}}}}
document.getElementById('loginButton').addEventListener('click',async()=>{{const ownerToken=tokenInput.value;tokenInput.value='';if(!ownerToken){{status('Enter the owner credential.','error');return;}}try{{const r=await fetch('/voice-console/session',{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'same-origin',body:JSON.stringify({{owner_token:ownerToken}})}});if(!r.ok){{showAuthenticated(false);status('Owner authentication failed.','error');return;}}showAuthenticated(true);status('Owner session active.','ok');}}catch(e){{showAuthenticated(false);status('Owner authentication failed.','error');}}}});
textInput.addEventListener('input',()=>{{count.textContent=`${{textInput.value.length}} / 4000`;}});
document.getElementById('speakButton').addEventListener('click',async()=>{{const text=textInput.value.trim();if(!text){{status('Enter text for SARA to speak.','error');return;}}if(controller) controller.abort();controller=new AbortController();releaseAudio();status('Synthesizing SARA voice…');try{{const r=await fetch('/voice-console/api/synthesize',{{method:'POST',headers:{{'Content-Type':'application/json'}},credentials:'same-origin',body:JSON.stringify({{text}}),signal:controller.signal}});if(r.status===401){{showAuthenticated(false);status('Owner session expired. Sign in again.','error');return;}}if(!r.ok){{let message='Voice synthesis failed.';try{{const body=await r.json();if(body.detail)message=body.detail;}}catch(_){{}}status(message,'error');return;}}const blob=await r.blob();audioUrl=URL.createObjectURL(blob);player.src=audioUrl;await player.play();status('SARA is speaking.','ok');}}catch(e){{if(e.name==='AbortError')status('Playback stopped.');else status('Voice synthesis failed.','error');}}finally{{controller=null;}}}});
document.getElementById('stopButton').addEventListener('click',()=>{{if(controller)controller.abort();player.pause();player.currentTime=0;status('Playback stopped.');}});
document.getElementById('logoutButton').addEventListener('click',async()=>{{if(controller)controller.abort();player.pause();releaseAudio();await fetch('/voice-console/session',{{method:'DELETE',credentials:'same-origin'}});showAuthenticated(false);status('Signed out.');tokenInput.focus();}});
player.addEventListener('ended',()=>status('Playback complete.','ok'));
sessionState();
</script>
</body>
</html>'''


def register_voice_console_routes(app) -> None:
    @app.get("/voice-console", response_class=HTMLResponse, include_in_schema=False)
    def voice_console_page() -> HTMLResponse:
        return HTMLResponse(VOICE_CONSOLE_HTML, headers=_security_headers())

    @app.get("/voice-console/session", include_in_schema=False)
    def voice_console_session_status(request: Request) -> JSONResponse:
        foreign_origin = _reject_foreign_origin(request)
        if foreign_origin is not None:
            return foreign_origin
        main_module = _main_module()
        authenticated = _session_valid(
            request,
            owner_token=main_module.OWNER_TOKEN,
            kill_switch=main_module.KILL_SWITCH,
        )
        return _json({"authenticated": authenticated})

    @app.post("/voice-console/session", include_in_schema=False)
    def voice_console_login(payload: VoiceConsoleLogin, request: Request) -> JSONResponse:
        foreign_origin = _reject_foreign_origin(request)
        if foreign_origin is not None:
            return foreign_origin
        main_module = _main_module()
        configured_owner_token = main_module.OWNER_TOKEN
        if (
            main_module.KILL_SWITCH
            or not configured_owner_token
            or not secrets.compare_digest(payload.owner_token, configured_owner_token)
        ):
            return _json({"detail": "Unauthorized"}, status_code=401)

        previous_session = request.cookies.get(VOICE_CONSOLE_COOKIE, "")
        _remove_session(previous_session)
        session_id = _new_session(configured_owner_token)
        response = _json({"authenticated": True})
        _set_session_cookie(response, session_id)
        return response

    @app.delete("/voice-console/session", include_in_schema=False)
    def voice_console_logout(request: Request) -> JSONResponse:
        foreign_origin = _reject_foreign_origin(request)
        if foreign_origin is not None:
            return foreign_origin
        _remove_session(request.cookies.get(VOICE_CONSOLE_COOKIE, ""))
        response = _json({"authenticated": False})
        _clear_session_cookie(response)
        return response

    @app.post("/voice-console/api/synthesize", include_in_schema=False)
    def voice_console_synthesize(payload: VoiceSynthesisRequest, request: Request):
        foreign_origin = _reject_foreign_origin(request)
        if foreign_origin is not None:
            return foreign_origin
        main_module = _main_module()
        current_owner_token = main_module.OWNER_TOKEN
        if not _session_valid(
            request,
            owner_token=current_owner_token,
            kill_switch=main_module.KILL_SWITCH,
        ):
            return _json({"detail": "Unauthorized"}, status_code=401)

        # Call the existing governed owner-only endpoint directly server-side.
        # This preserves its authorization, kill-switch, input limits, audit digest,
        # Piper isolation, and error behavior without exposing OWNER_TOKEN to JS.
        owner_request = SimpleNamespace(headers={"Authorization": f"Bearer {current_owner_token}"})
        response = main_module.piper_voice_synthesize(payload, owner_request)
        for name, value in _security_headers().items():
            response.headers[name] = value
        return response
