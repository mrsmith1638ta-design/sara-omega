"""SARA OMEGA v2.5.2 + SIOS V3.2 fail-safe hardening - Railway Production."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.cloud import speech, texttospeech, vision, translate_v2 as translate
from openai import OpenAI

from sara_v32_hardening import BackupError, FailSafeEvent, RuntimeFailSafe

BASE_VERSION = "2.5.2"
HARDENING_PROFILE = "SIOS-V3.2-FAILSAFE-1"
DISPLAY_VERSION = f"{BASE_VERSION}+{HARDENING_PROFILE.lower()}"

logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')
logger = logging.getLogger(__name__)

OWNER_TOKEN = os.environ.get("OWNER_TOKEN", "")
TEST_TOKEN = os.environ.get("TEST_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
KILL_SWITCH = os.environ.get("KILL_SWITCH", "false").lower() == "true"
FEATURE_VISION = os.environ.get("FEATURE_VISION", "true").lower() == "true"
SIOS_BASE_URL = os.environ.get("SIOS_BASE_URL", "").strip()
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024

RATE_LIMITS = {
    "owner": {"requests_per_day": None, "voice_per_day": None, "vision_per_day": None, "max_context": None},
    "tester": {"requests_per_day": 200, "voice_per_day": 30, "vision_per_day": 50, "max_context": 50},
}

app = FastAPI(title="SARA OMEGA", version=DISPLAY_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

stt_client = tts_client = vision_client = translate_client = llm_client = None
try:
    stt_client = speech.SpeechClient()
    tts_client = texttospeech.TextToSpeechClient()
    vision_client = vision.ImageAnnotatorClient()
    translate_client = translate.Client()
    if OPENAI_API_KEY:
        llm_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("Clients initialized")
except Exception as exc:
    logger.error("Init error: %s", type(exc).__name__)

SESSION: Dict[str, List[Dict[str, str]]] = {}
AUDIT: List[Dict] = []
RATE_LIMIT = defaultdict(list)
startup_time = time.time()
FAILSAFE = RuntimeFailSafe.from_env()


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha512_hash(data: str) -> str:
    return hashlib.sha512(data.encode()).hexdigest()


def clean_text(text: str, max_length: int = 500) -> str:
    return re.sub(r'[<>{}[\]\\`]', '', text)[:max_length].strip()


def authorize(req: Request) -> Optional[str]:
    if KILL_SWITCH:
        return None
    auth = req.headers.get("Authorization", "")
    if OWNER_TOKEN and auth == f"Bearer {OWNER_TOKEN}":
        return "owner"
    if TEST_TOKEN and auth == f"Bearer {TEST_TOKEN}":
        return "tester"
    return None


def runtime_state() -> Dict:
    return {
        "session": SESSION,
        "audit": AUDIT,
        "rate_limit": {key: list(values) for key, values in RATE_LIMIT.items()},
        "base_version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
    }


def failsafe_checkpoint(event: FailSafeEvent, *, correlation_id: str = "", metadata: Optional[Dict] = None):
    try:
        return FAILSAFE.checkpoint(runtime_state(), event, correlation_id=correlation_id, metadata=metadata or {})
    except BackupError:
        if FAILSAFE.required:
            raise
        logger.exception("Optional fail-safe checkpoint failed")
        return None


def audit(event: str, details: Optional[Dict] = None):
    timestamp = int(time.time())
    entry = {
        "timestamp": timestamp,
        "iso_time": utc_iso(),
        "event": clean_text(event, 128),
        "details": details or {},
        "hash": sha512_hash(f"{event}:{timestamp}"),
    }
    AUDIT.append(entry)
    if len(AUDIT) > 1000:
        AUDIT.pop(0)


def check_rate_limit(identifier: str, role: str, limit_type: str = "requests") -> bool:
    limits = RATE_LIMITS.get(role, RATE_LIMITS["tester"])
    if role == "owner":
        return True
    if limit_type == "voice":
        daily_limit = limits["voice_per_day"]
    elif limit_type == "vision":
        daily_limit = limits["vision_per_day"]
    else:
        daily_limit = limits["requests_per_day"]
    now = time.time()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    key = f"{identifier}:{limit_type}"
    requests = [t for t in RATE_LIMIT[key] if t > today_start]
    if daily_limit and len(requests) >= daily_limit:
        return False
    failsafe_checkpoint(
        FailSafeEvent.PRE_MUTATION,
        correlation_id=f"rate-{uuid.uuid4()}",
        metadata={"store": "rate_limit", "limit_type": limit_type, "role": role},
    )
    RATE_LIMIT[key].append(now)
    return True


def get_max_context(role: str) -> int:
    limits = RATE_LIMITS.get(role, RATE_LIMITS["tester"])
    max_ctx = limits["max_context"]
    return max_ctx if max_ctx else 1000


def think(session_id: str, text: str, role: str = "tester") -> str:
    if not llm_client:
        return "AI not configured. Set OPENAI_API_KEY."
    try:
        ctx = list(SESSION.get(session_id, []))
        ctx.append({"role": "user", "content": clean_text(text, 1000)})
        max_context = get_max_context(role)
        ctx = ctx[-max_context:] if max_context else ctx
        response = llm_client.chat.completions.create(model="gpt-4o-mini", messages=ctx, temperature=0.6, max_tokens=500)
        answer = response.choices[0].message.content or ""
        ctx.append({"role": "assistant", "content": answer})
        failsafe_checkpoint(
            FailSafeEvent.PRE_MUTATION,
            correlation_id=f"session-{uuid.uuid4()}",
            metadata={"store": "session", "session_id": clean_text(session_id, 128), "role": role},
        )
        SESSION[session_id] = ctx
        audit(
            "llm_completion",
            {
                "session_id": clean_text(session_id, 128),
                "tokens": getattr(response.usage, "total_tokens", None),
                "role": role,
                "epistemic_status": "UNVERIFIED",
                "execution_authority": False,
            },
        )
        return answer
    except BackupError as exc:
        logger.error("Fail-safe blocked session mutation: %s", type(exc).__name__)
        return "Request blocked because fail-safe state protection is unavailable."
    except Exception as exc:
        logger.error("Think error: %s", type(exc).__name__)
        return "Error processing request."


@app.middleware("http")
async def failsafe_exception_boundary(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        try:
            failsafe_checkpoint(
                FailSafeEvent.UNHANDLED_EXCEPTION,
                correlation_id=request.headers.get("X-Request-Id", str(uuid.uuid4())),
                metadata={"method": request.method, "path": request.url.path, "exception_type": type(exc).__name__},
            )
        except Exception:
            logger.exception("Fail-safe exception checkpoint also failed")
        raise


@app.on_event("shutdown")
def shutdown_checkpoint():
    try:
        failsafe_checkpoint(FailSafeEvent.SHUTDOWN, correlation_id=f"shutdown-{uuid.uuid4()}")
    except Exception:
        logger.exception("Shutdown fail-safe checkpoint failed")


@app.get("/")
def root():
    return {
        "name": "SARA OMEGA",
        "version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "status": "online" if not KILL_SWITCH else "disabled",
        "platform": "Railway",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "platform": "Railway",
        "timestamp": utc_iso(),
        "uptime": int(time.time() - startup_time),
        "dependencies": {
            "google_cloud": stt_client is not None,
            "openai": llm_client is not None,
            "sios_configured": bool(SIOS_BASE_URL),
        },
        "features": {"voice": True, "vision": FEATURE_VISION},
        "failsafe": FAILSAFE.status(),
        "kill_switch": KILL_SWITCH,
    }


@app.get("/health/ready")
def readiness():
    if KILL_SWITCH:
        raise HTTPException(503, "Service disabled")
    try:
        FAILSAFE.ensure_ready()
    except BackupError as exc:
        raise HTTPException(503, f"Fail-safe unavailable: {type(exc).__name__}") from exc
    return {"ready": True, "failsafe": FAILSAFE.status(), "hardening_profile": HARDENING_PROFILE}


@app.get("/health/live")
def liveness():
    return {"alive": True}


@app.get("/metrics")
def metrics():
    configured = 1 if FAILSAFE.configured else 0
    return Response(
        f"sara_active_sessions {len(SESSION)}\n"
        f"sara_audit_entries {len(AUDIT)}\n"
        f"sara_failsafe_configured {configured}\n",
        media_type="text/plain",
    )


@app.post("/voice")
async def voice(req: Request, file: UploadFile, session_id: str, location: str = ""):
    if not (role := authorize(req)):
        raise HTTPException(401, "Unauthorized")
    if not check_rate_limit(f"voice:{session_id}", role, "voice"):
        raise HTTPException(429, f"Daily voice limit reached ({RATE_LIMITS[role]['voice_per_day']} per day)")
    if not stt_client or not tts_client:
        raise HTTPException(503, "Voice unavailable")
    try:
        audio = await file.read()
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "Audio too large")
        rec = speech.RecognitionAudio(content=audio)
        cfg = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )
        stt_response = stt_client.recognize(config=cfg, audio=rec)
        if not stt_response.results:
            return JSONResponse(status_code=400, content={"error": "No speech"})
        transcript = " ".join([r.alternatives[0].transcript for r in stt_response.results])
        reply = think(session_id, transcript, role)
        synthesis = texttospeech.SynthesisInput(text=reply)
        voice_params = texttospeech.VoiceSelectionParams(language_code="en-GB", name="en-GB-Wavenet-C")
        audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        tts_response = tts_client.synthesize_speech(input=synthesis, voice=voice_params, audio_config=audio_cfg)
        audit("voice_interaction", {"session_id": clean_text(session_id, 128), "role": role})
        return Response(tts_response.audio_content, media_type="audio/mpeg")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, "Voice processing failed") from exc


@app.post("/vision")
async def vision_read(req: Request, file: UploadFile, target_lang: str = "en"):
    if not (role := authorize(req)):
        raise HTTPException(401, "Unauthorized")
    if not FEATURE_VISION:
        raise HTTPException(403, "Vision disabled")
    identifier = f"vision:{req.client.host if req.client else 'unknown'}"
    if not check_rate_limit(identifier, role, "vision"):
        raise HTTPException(429, f"Daily vision limit reached ({RATE_LIMITS[role]['vision_per_day']} per day)")
    if not vision_client:
        raise HTTPException(503, "Vision unavailable")
    try:
        content = await file.read()
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image too large")
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        if not response.text_annotations:
            return {"original_text": "", "message": "No text"}
        text = response.text_annotations[0].description
        translated = (
            translate_client.translate(text, target_language=target_lang)["translatedText"]
            if target_lang != "en" and translate_client
            else text
        )
        audit("vision_ocr", {"role": role, "target_lang": clean_text(target_lang, 16)})
        return {"original_text": text, "translated_text": translated, "target_language": target_lang}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, "Vision processing failed") from exc


@app.get("/admin/stats")
def admin_stats(req: Request):
    if authorize(req) != "owner":
        raise HTTPException(403, "Owner only")
    return {
        "version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "platform": "Railway",
        "uptime": int(time.time() - startup_time),
        "sessions": len(SESSION),
        "audit": len(AUDIT),
        "rate_limits": RATE_LIMITS,
        "features": {"voice": stt_client is not None, "vision": vision_client is not None},
        "failsafe": FAILSAFE.status(),
        "kill_switch": KILL_SWITCH,
    }


@app.get("/admin/failsafe/status")
def failsafe_status(req: Request):
    if authorize(req) != "owner":
        raise HTTPException(403, "Owner only")
    result = FAILSAFE.status()
    if FAILSAFE.configured:
        try:
            result["chain_valid"] = FAILSAFE.verify_retained_chain()
        except BackupError:
            result["chain_valid"] = False
    else:
        result["chain_valid"] = None
    return result


@app.post("/admin/failsafe/checkpoint")
def manual_failsafe_checkpoint(req: Request):
    if authorize(req) != "owner":
        raise HTTPException(403, "Owner only")
    try:
        receipt = failsafe_checkpoint(
            FailSafeEvent.MANUAL,
            correlation_id=req.headers.get("X-Request-Id", str(uuid.uuid4())),
            metadata={"initiator": "owner"},
        )
    except BackupError as exc:
        raise HTTPException(503, f"Fail-safe checkpoint unavailable: {type(exc).__name__}") from exc
    if receipt is None:
        raise HTTPException(503, "Fail-safe controller is not configured")
    audit("failsafe_manual_checkpoint", {"snapshot_id": receipt.snapshot_id})
    return {
        "snapshot_id": receipt.snapshot_id,
        "created_at": receipt.created_at,
        "state_sha3_512": receipt.state_sha3_512,
        "chain_digest": receipt.chain_digest,
    }


@app.post("/admin/failsafe/restore-latest")
def restore_latest(req: Request):
    if authorize(req) != "owner":
        raise HTTPException(403, "Owner only")
    try:
        failsafe_checkpoint(
            FailSafeEvent.PRE_MUTATION,
            correlation_id=req.headers.get("X-Request-Id", str(uuid.uuid4())),
            metadata={"store": "runtime", "operation": "restore_latest"},
        )
        result = FAILSAFE.restore_latest()
    except BackupError as exc:
        raise HTTPException(503, f"Fail-safe restore unavailable: {type(exc).__name__}") from exc
    restored = result.state
    sessions = restored.get("session")
    audit_entries = restored.get("audit")
    rate_limit = restored.get("rate_limit")
    if not isinstance(sessions, dict) or not isinstance(audit_entries, list) or not isinstance(rate_limit, dict):
        raise HTTPException(409, "Snapshot runtime schema is invalid")
    SESSION.clear()
    SESSION.update(sessions)
    AUDIT.clear()
    AUDIT.extend(audit_entries[-1000:])
    RATE_LIMIT.clear()
    for key, values in rate_limit.items():
        if isinstance(key, str) and isinstance(values, list) and all(isinstance(v, (int, float)) for v in values):
            RATE_LIMIT[key] = list(values)
    audit(
        "failsafe_restore",
        {"snapshot_id": result.snapshot_id, "fallback_used": result.fallback_used, "authority_revalidated": True},
    )
    return {
        "restored": True,
        "snapshot_id": result.snapshot_id,
        "fallback_used": result.fallback_used,
        "authority_note": "Restored state does not bypass current request authentication or current execution gates.",
    }
