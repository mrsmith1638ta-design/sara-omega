"""SARA-OMEGA V3.2.1 - SIOS V3.2 fail-safe + Railway zero-to-production release."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

try:
    from google.cloud import speech, texttospeech, vision, translate_v2 as translate
    GCP_IMPORT_ERROR = ""
except Exception as exc:
    speech = texttospeech = vision = translate = None
    GCP_IMPORT_ERROR = type(exc).__name__

try:
    from openai import OpenAI
    OPENAI_IMPORT_ERROR = ""
except Exception as exc:
    OpenAI = None
    OPENAI_IMPORT_ERROR = type(exc).__name__

from context_dev_resolver import (
    PENDING_CONTEXT_DEV_LICENSE,
    RequestContext,
    evaluate_request,
)
from sara_v32_hardening import BackupError, FailSafeEvent, RuntimeFailSafe
from app.enterprise_runtime import (
    concentration_governor,
    hawkins_chaos,
    module_awareness,
    router as enterprise_runtime_router,
    runtime_assurance,
    titan,
)
from app.concentration import ConcentrationRequest
from app.hawkins_chaos import HawkinsChaosRequest
from app.models import Problem
from app.orchestrator import SaraOmega
from app.runtime_assurance import RuntimeAssuranceConfigurationError, RuntimeAssuranceRequest

BASE_VERSION = "2.5.2"
RELEASE_VERSION = "3.2.1"
HARDENING_PROFILE = "SIOS-V3.2-FAILSAFE-1"
DISPLAY_VERSION = RELEASE_VERSION

logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')
logger = logging.getLogger(__name__)

OWNER_TOKEN = os.environ.get("OWNER_TOKEN", "")
GPT_ACTION_TOKEN = os.environ.get("GPT_ACTION_TOKEN", "")
TEST_TOKEN = os.environ.get("TEST_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
KILL_SWITCH = os.environ.get("KILL_SWITCH", "false").lower() == "true"
FEATURE_VISION = os.environ.get("FEATURE_VISION", "false").lower() == "true"
ENABLE_GCP = os.environ.get("ENABLE_GCP", "false").lower() == "true"
SIOS_BASE_URL = os.environ.get("SIOS_BASE_URL", "").strip()
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024

RATE_LIMITS = {
    "owner": {"requests_per_day": None, "voice_per_day": None, "vision_per_day": None, "max_context": None},
    "action": {"requests_per_day": 500, "voice_per_day": 0, "vision_per_day": 0, "max_context": 50},
    "tester": {"requests_per_day": 200, "voice_per_day": 30, "vision_per_day": 50, "max_context": 50},
}

app = FastAPI(title="SARA OMEGA", version=DISPLAY_VERSION)
app.include_router(enterprise_runtime_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

stt_client = tts_client = vision_client = translate_client = llm_client = None
gcp_init_error = GCP_IMPORT_ERROR
openai_init_error = OPENAI_IMPORT_ERROR
gateway_sara = SaraOmega()

GPTActionOperation = Literal[
    "status",
    "production_acceptance",
    "module_awareness",
    "runtime_assurance",
    "concentration",
    "hawkins_chaos",
    "titan_health",
    "solve",
    "verify_output",
]


class GPTActionGatewayRequest(BaseModel):
    operation: GPTActionOperation = Field(
        description="The governed SARA backend operation ChatGPT is requesting."
    )
    query: str | None = Field(default=None, description="User request to route through SARA Omega.")
    objective: str | None = Field(default=None, description="Optional explicit outcome for solve requests.")
    requested_action: str | None = Field(default=None, description="Optional action intent for governance.")
    module: str = Field(default="sara-chatgpt-action", max_length=256)
    output: str | None = Field(default=None, description="Generated text to verify before ChatGPT repeats it.")
    context: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    fail_closed: bool = True
    council: bool | None = None
    session_id: str | None = Field(default=None, max_length=256)


def get_llm_client():
    global llm_client, openai_init_error
    if llm_client is not None:
        return llm_client
    if OpenAI is None:
        openai_init_error = OPENAI_IMPORT_ERROR or "ImportError"
        return None
    if not OPENAI_API_KEY:
        return None
    try:
        llm_client = OpenAI(api_key=OPENAI_API_KEY)
        openai_init_error = ""
        return llm_client
    except Exception as exc:
        openai_init_error = type(exc).__name__
        logger.error("OpenAI lazy init error: %s", openai_init_error)
        return None


def get_voice_clients():
    global stt_client, tts_client, gcp_init_error
    if not ENABLE_GCP:
        return None, None
    if speech is None or texttospeech is None:
        gcp_init_error = GCP_IMPORT_ERROR or "ImportError"
        return None, None
    if stt_client is not None and tts_client is not None:
        return stt_client, tts_client
    try:
        if stt_client is None:
            stt_client = speech.SpeechClient()
        if tts_client is None:
            tts_client = texttospeech.TextToSpeechClient()
        gcp_init_error = ""
        return stt_client, tts_client
    except Exception as exc:
        gcp_init_error = type(exc).__name__
        logger.error("Google voice lazy init error: %s", gcp_init_error)
        return None, None


def get_vision_clients():
    global vision_client, translate_client, gcp_init_error
    if not ENABLE_GCP or not FEATURE_VISION:
        return None, None
    if vision is None or translate is None:
        gcp_init_error = GCP_IMPORT_ERROR or "ImportError"
        return None, None
    if vision_client is not None:
        return vision_client, translate_client
    try:
        vision_client = vision.ImageAnnotatorClient()
        translate_client = translate.Client()
        gcp_init_error = ""
        return vision_client, translate_client
    except Exception as exc:
        gcp_init_error = type(exc).__name__
        logger.error("Google vision lazy init error: %s", gcp_init_error)
        return None, None

SESSION: Dict[str, List[Dict[str, str]]] = {}
AUDIT: List[Dict] = []
RATE_LIMIT = defaultdict(list)
startup_time = time.time()
FAILSAFE = RuntimeFailSafe.from_env()
CONTEXT_DEV_LICENSE = PENDING_CONTEXT_DEV_LICENSE


class ContextDevEvaluationRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    monetized: bool = True
    automated_use: bool = True
    target_site_rights_valid: bool = False
    sensitive: bool = False
    requires_zdr: bool = False
    zdr_entitlement_verified: bool = False
    zdr_endpoint_verified: bool = False
    requested_scopes: list[str] = Field(default_factory=list, max_length=32)


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
    if GPT_ACTION_TOKEN and auth == f"Bearer {GPT_ACTION_TOKEN}":
        return "action"
    if TEST_TOKEN and auth == f"Bearer {TEST_TOKEN}":
        return "tester"
    return None


def runtime_state() -> Dict:
    return {
        "session": SESSION,
        "audit": AUDIT,
        "rate_limit": {key: list(values) for key, values in RATE_LIMIT.items()},
        "base_version": BASE_VERSION,
        "release_version": RELEASE_VERSION,
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


def require_action_role(req: Request) -> str:
    role = authorize(req)
    if not role:
        raise HTTPException(401, "Unauthorized")
    return role


def ensure_action_ready(operation: str) -> None:
    try:
        FAILSAFE.ensure_ready()
    except BackupError as exc:
        raise HTTPException(
            503,
            f"SARA action gateway is fail-closed because the fail-safe is unavailable: {type(exc).__name__}",
        ) from exc
    if operation in {"solve", "verify_output"}:
        try:
            failsafe_checkpoint(
                FailSafeEvent.PRE_MUTATION,
                correlation_id=f"gpt-action-{uuid.uuid4()}",
                metadata={"gateway": "chatgpt_action", "operation": operation},
            )
        except BackupError as exc:
            raise HTTPException(
                503,
                f"SARA action gateway blocked mutation before execution: {type(exc).__name__}",
            ) from exc


def production_acceptance_snapshot() -> Dict[str, Any]:
    root = Path(str(FAILSAFE.root)).expanduser()
    evidence_path = root / "production-acceptance.json"
    if evidence_path.exists():
        try:
            with evidence_path.open("r", encoding="utf-8") as handle:
                evidence = json.load(handle)
            public_keys = {
                "project_name",
                "release_version",
                "hardening_profile",
                "bootstrap_ready",
                "production_accepted",
                "failsafe_required",
                "failsafe_configured",
                "owner_token_configured",
                "dedicated_mount_required",
                "root_on_dedicated_mount",
                "checkpoint_self_test",
                "chain_valid",
                "persistence_observed_across_boots",
                "persistence_status",
            }
            return {key: evidence.get(key) for key in sorted(public_keys) if key in evidence}
        except Exception as exc:
            return {"production_accepted": False, "evidence_read_error": type(exc).__name__}
    status = FAILSAFE.status()
    return {
        "production_accepted": False,
        "persistence_status": "EVIDENCE_FILE_NOT_FOUND",
        "failsafe_required": status.get("required"),
        "failsafe_configured": status.get("configured"),
    }


def model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return value


def gateway_status() -> Dict[str, Any]:
    router = runtime_assurance.router_state()
    return {
        "service": "sara-chatgpt-action-gateway",
        "status": "online" if not KILL_SWITCH else "disabled",
        "architecture": "SARA inside ChatGPT frame with Railway V3.2.1 as governed backend brain.",
        "version": RELEASE_VERSION,
        "base_runtime_version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "platform": "Railway",
        "production_acceptance": production_acceptance_snapshot(),
        "runtime_assurance": {
            "policy": router.get("policy"),
            "active_evidence_domains": [
                domain["domain"] for domain in router.get("domains", []) if domain.get("active")
            ],
        },
        "module_awareness": module_awareness.count(),
        "concentration_governor": concentration_governor.health(),
        "hawkins_chaos": hawkins_chaos.health(),
        "titan": titan.health(),
        "allowed_operations": list(GPTActionOperation.__args__),
    }


@app.post("/gpt/action/gateway")
async def chatgpt_action_gateway(req: Request, body: GPTActionGatewayRequest):
    role = require_action_role(req)
    ensure_action_ready(body.operation)

    identifier = f"gpt-action:{body.session_id or (req.client.host if req.client else 'unknown')}"
    if body.operation in {"solve", "verify_output"} and not check_rate_limit(identifier, role, "requests"):
        raise HTTPException(429, f"Daily action limit reached ({RATE_LIMITS[role]['requests_per_day']} per day)")

    if body.operation == "status":
        return gateway_status()

    if body.operation == "production_acceptance":
        return {
            "service": "sara-chatgpt-action-gateway",
            "production_acceptance": production_acceptance_snapshot(),
        }

    if body.operation == "module_awareness":
        return {
            "service": "sara-chatgpt-action-gateway",
            "count": module_awareness.count(),
            "awareness": module_awareness.awareness(),
            "diff": module_awareness.diff(),
        }

    if body.operation == "runtime_assurance":
        return runtime_assurance.router_state(body.context)

    if body.operation == "concentration":
        objective = (body.objective or body.query or "").strip()
        output = (body.output or body.query or "").strip()
        if not objective or not output:
            raise HTTPException(400, "objective/query and output/query are required for concentration")
        return concentration_governor.analyze(
            ConcentrationRequest(
                objective=objective,
                output=output,
                constraints=list(body.context.get("constraints", [])),
                context=body.context,
                threshold=float(body.context.get("focus_threshold", 0.72)),
            )
        )

    if body.operation == "hawkins_chaos":
        return hawkins_chaos.analyze(
            HawkinsChaosRequest(
                state={
                    "query": body.query or body.output or "",
                    "confidence": body.context.get("confidence", body.context.get("epistemic_confidence", 0.5)),
                    "decision": body.context.get("decision", ""),
                    "governance": body.context.get("governance", {}),
                    "context": body.context,
                },
                evidence=body.evidence,
                action={"requested_action": body.requested_action} if body.requested_action else {},
            )
        )

    if body.operation == "titan_health":
        return titan.health()

    if body.operation == "verify_output":
        output = (body.output or body.query or "").strip()
        if not output:
            raise HTTPException(400, "output is required for verify_output")
        try:
            verdict = await runtime_assurance.verify_output(
                RuntimeAssuranceRequest(
                    module=body.module,
                    output=output,
                    context=body.context,
                    evidence=body.evidence,
                    fail_closed=body.fail_closed,
                )
            )
        except RuntimeAssuranceConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        audit(
            "gpt_action_verify_output",
            {
                "module": clean_text(body.module, 128),
                "role": role,
                "verdict": verdict.get("verdict"),
                "action": verdict.get("action"),
            },
        )
        return verdict

    query = (body.query or "").strip()
    if not query:
        raise HTTPException(400, "query is required for solve")
    problem_context = dict(body.context)
    problem_context.setdefault("source", "chatgpt_action_gateway")
    problem_context.setdefault("railway_runtime_version", RELEASE_VERSION)
    problem = Problem(
        query=query,
        objective=body.objective,
        requested_action=body.requested_action,
        context=problem_context,
        council=body.council,
        actor="chatgpt_action",
        authority_level=3 if role == "owner" else 1,
    )
    verdict = await gateway_sara.solve(problem)
    chaos = hawkins_chaos.analyze_verdict(verdict, query=query, context=problem_context)
    concentration = concentration_governor.analyze_verdict(
        objective=body.objective or query,
        verdict=verdict,
        context=problem_context,
    )
    audit(
        "gpt_action_solve",
        {
            "role": role,
            "decision": getattr(verdict, "decision", ""),
            "decision_id": getattr(verdict, "decision_id", ""),
            "hawkins_effective_authority": chaos.get("effective_authority"),
            "focus_score": concentration.get("focus_score"),
            "refocus_required": concentration.get("refocus_required"),
        },
    )
    return {
        "service": "sara-chatgpt-action-gateway",
        "operation": "solve",
        "verdict": model_dump(verdict),
        "concentration_governor": concentration,
        "hawkins_chaos": chaos,
    }


@app.get("/gpt/action/openapi.yaml", include_in_schema=False)
def chatgpt_action_openapi_schema():
    schema_path = Path(__file__).with_name("chatgpt-gpt-action.yaml")
    return Response(schema_path.read_text(encoding="utf-8"), media_type="text/yaml")


def think(session_id: str, text: str, role: str = "tester") -> str:
    client = get_llm_client()
    if not client:
        return "AI not configured. Set OPENAI_API_KEY."
    try:
        ctx = list(SESSION.get(session_id, []))
        ctx.append({"role": "user", "content": clean_text(text, 1000)})
        max_context = get_max_context(role)
        ctx = ctx[-max_context:] if max_context else ctx
        response = client.chat.completions.create(model="gpt-4o-mini", messages=ctx, temperature=0.6, max_tokens=500)
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
        "version": RELEASE_VERSION,
        "base_runtime_version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "status": "online" if not KILL_SWITCH else "disabled",
        "platform": "Railway",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": RELEASE_VERSION,
        "base_runtime_version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "platform": "Railway",
        "timestamp": utc_iso(),
        "uptime": int(time.time() - startup_time),
        "dependencies": {
            "google_cloud": ENABLE_GCP,
            "openai": bool(OPENAI_API_KEY),
            "sios_configured": bool(SIOS_BASE_URL),
            "context_dev_commercial_runtime": False,
        },
        "features": {
            "voice": ENABLE_GCP,
            "vision": ENABLE_GCP and FEATURE_VISION,
            "context_dev_policy_gate": True,
        },
        "context_dev": CONTEXT_DEV_LICENSE.public_status(),
        "client_state": {
            "voice_initialized": stt_client is not None and tts_client is not None,
            "vision_initialized": vision_client is not None,
            "openai_initialized": llm_client is not None,
            "gcp_last_error": gcp_init_error,
            "openai_last_error": openai_init_error,
        },
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
    return {"ready": True, "version": RELEASE_VERSION, "base_runtime_version": BASE_VERSION, "failsafe": FAILSAFE.status(), "hardening_profile": HARDENING_PROFILE}


@app.get("/health/live")
def liveness():
    return {"alive": True}


@app.get("/context-dev/status")
def context_dev_status():
    """Return non-secret authorization state; this endpoint never enables use."""
    return CONTEXT_DEV_LICENSE.public_status()


@app.post("/context-dev/evaluate")
def context_dev_evaluate(payload: ContextDevEvaluationRequest, req: Request):
    """Owner-only dry evaluation. No Context.dev network transport exists here."""
    if authorize(req) != "owner":
        raise HTTPException(403, "Owner only")
    requested_scopes = frozenset(
        clean_text(scope, 128)
        for scope in payload.requested_scopes
        if clean_text(scope, 128)
    )
    decision = evaluate_request(
        RequestContext(
            request_id=clean_text(payload.request_id, 128),
            monetized=payload.monetized,
            automated_use=payload.automated_use,
            target_site_rights_valid=payload.target_site_rights_valid,
            sensitive=payload.sensitive,
            requires_zdr=payload.requires_zdr,
            zdr_entitlement_verified=payload.zdr_entitlement_verified,
            zdr_endpoint_verified=payload.zdr_endpoint_verified,
            requested_scopes=requested_scopes,
        ),
        CONTEXT_DEV_LICENSE,
    )
    return decision.as_dict()


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
    active_stt_client, active_tts_client = get_voice_clients()
    if not active_stt_client or not active_tts_client:
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
        stt_response = active_stt_client.recognize(config=cfg, audio=rec)
        if not stt_response.results:
            return JSONResponse(status_code=400, content={"error": "No speech"})
        transcript = " ".join([r.alternatives[0].transcript for r in stt_response.results])
        reply = think(session_id, transcript, role)
        synthesis = texttospeech.SynthesisInput(text=reply)
        voice_params = texttospeech.VoiceSelectionParams(language_code="en-GB", name="en-GB-Wavenet-C")
        audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        tts_response = active_tts_client.synthesize_speech(input=synthesis, voice=voice_params, audio_config=audio_cfg)
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
    active_vision_client, active_translate_client = get_vision_clients()
    if not active_vision_client:
        raise HTTPException(503, "Vision unavailable")
    try:
        content = await file.read()
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image too large")
        image = vision.Image(content=content)
        response = active_vision_client.text_detection(image=image)
        if not response.text_annotations:
            return {"original_text": "", "message": "No text"}
        text = response.text_annotations[0].description
        translated = (
            active_translate_client.translate(text, target_language=target_lang)["translatedText"]
            if target_lang != "en" and active_translate_client
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
        "version": RELEASE_VERSION,
        "base_runtime_version": BASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "platform": "Railway",
        "uptime": int(time.time() - startup_time),
        "sessions": len(SESSION),
        "audit": len(AUDIT),
        "rate_limits": RATE_LIMITS,
        "features": {
            "voice": ENABLE_GCP,
            "vision": ENABLE_GCP and FEATURE_VISION,
            "context_dev_policy_gate": True,
        },
        "context_dev": CONTEXT_DEV_LICENSE.public_status(),
        "client_state": {
            "voice_initialized": stt_client is not None and tts_client is not None,
            "vision_initialized": vision_client is not None,
            "openai_initialized": llm_client is not None,
            "gcp_last_error": gcp_init_error,
            "openai_last_error": openai_init_error,
        },
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
