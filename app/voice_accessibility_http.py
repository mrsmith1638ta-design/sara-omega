from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from sara_unified.api.schemas import (
    VoiceAccessibilityEntitlementRequest,
    VoiceAccessibilityJobRequest,
    VoiceAccessibilityPreferencesRequest,
)
from sara_unified.config import Settings
from sara_unified.voice.client import PiperVoiceClient
from sara_unified.voice.jobs import VoiceJobManager
from sara_unified.voice.segmenting import split_sentences
from sara_v32_hardening import BackupError, FailSafeEvent, RuntimeFailSafe

from .memory import MemoryKeyError
from .user_identity import IdentityStoreError, OAuthPrincipal, OAuthRejected, UserIdentityStore
from .voice_accessibility import (
    VoiceAccessContext,
    VoiceAccessRejected,
    VoiceAccessStoreError,
    VoiceAccessibilityStore,
    VoicePreferences,
    VoiceRateLimitRejected,
    VoiceUsageLimits,
)


router = APIRouter()
VOICE_SCOPE = "sara.voice.accessibility"
VOICE_1_1_ACCEPTED_COMMIT_SHA = "3b8948894cf7a93472a7289079ae41ba99c2a096"
VOICE_JOB_RETENTION_SECONDS = 900
VOICE_JOB_MAX_ITEMS = 100
VOICE_LEASE_GRACE_SECONDS = 30
_voice_job_manager: VoiceJobManager | None = None


def _require_release() -> Settings:
    release_flags = (
        os.getenv("SARA_VOICE_1_1_ENABLED", "false").lower() == "true",
        os.getenv("SARA_VOICE_1_1A_ENABLED", "false").lower() == "true",
        os.getenv("SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED", "false").lower() == "true",
    )
    if not all(release_flags):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility configuration unavailable") from exc
    if os.getenv("SARA_VOICE_1_1_ACCEPTED_COMMIT_SHA", "").strip() != VOICE_1_1_ACCEPTED_COMMIT_SHA:
        raise HTTPException(status_code=503, detail="Voice 1.1 acceptance unavailable")
    return settings


def _bearer(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="SARA OAuth authentication required")
    token = authorization[7:].strip()
    if not token or len(token) > 1024:
        raise HTTPException(status_code=401, detail="SARA OAuth authentication required")
    return token


def _identity_store() -> UserIdentityStore:
    try:
        store = UserIdentityStore.from_env(required=True)
    except (MemoryKeyError, IdentityStoreError) as exc:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable") from exc
    if store is None:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable")
    return store


def _voice_store() -> VoiceAccessibilityStore:
    try:
        store = VoiceAccessibilityStore.from_env(required=True)
    except (MemoryKeyError, VoiceAccessStoreError) as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility persistence unavailable") from exc
    if store is None:
        raise HTTPException(status_code=503, detail="Voice accessibility persistence unavailable")
    return store


def _principal(request: Request) -> OAuthPrincipal:
    try:
        return _identity_store().resolve_access_token(_bearer(request))
    except HTTPException:
        _audit_rejection("AUTHENTICATION_REJECTED", actor="anonymous", reason_code="oauth_missing")
        raise
    except OAuthRejected as exc:
        _audit_rejection("AUTHENTICATION_REJECTED", actor="anonymous", reason_code="oauth_rejected")
        raise HTTPException(status_code=401, detail="SARA OAuth authentication rejected") from exc
    except IdentityStoreError as exc:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable") from exc


def _require_voice_scope(principal: OAuthPrincipal) -> None:
    if VOICE_SCOPE not in frozenset(principal.scope.split()):
        _audit_rejection(
            "AUTHORIZATION_REJECTED",
            actor=principal.public_user_id,
            reason_code="scope_missing",
            target_user=principal.user_uuid,
        )
        raise HTTPException(status_code=403, detail="Voice accessibility scope rejected")


def _access(principal: OAuthPrincipal) -> VoiceAccessContext:
    try:
        return _voice_store().resolve_access(principal.user_uuid)
    except VoiceAccessRejected as exc:
        _audit_rejection(
            "ENTITLEMENT_REJECTED",
            actor=principal.public_user_id,
            reason_code="entitlement_rejected",
            target_user=principal.user_uuid,
        )
        raise HTTPException(status_code=403, detail="Voice accessibility entitlement rejected") from exc
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility persistence unavailable") from exc


def _authorized_access(request: Request) -> tuple[OAuthPrincipal, VoiceAccessContext]:
    _require_release()
    principal = _principal(request)
    _require_voice_scope(principal)
    return principal, _access(principal)


def _owner(request: Request) -> None:
    expected = os.getenv("OWNER_TOKEN", "")
    authorization = request.headers.get("Authorization", "")
    if not authorization:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    supplied = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Owner only")


def _checkpoint(operation: str, event: FailSafeEvent, *, actor_hash: str) -> None:
    try:
        failsafe = RuntimeFailSafe.from_env()
        if not failsafe.configured:
            raise BackupError("failsafe_not_configured")
        failsafe.ensure_ready()
        failsafe.checkpoint(
            {"voice_accessibility": {"operation": operation, "actor_hash": actor_hash}},
            event,
            correlation_id=f"voice-1-1a-{uuid.uuid4()}",
            metadata={"gateway": "voice_1_1a", "operation": operation},
        )
    except BackupError as exc:
        raise HTTPException(status_code=503, detail="SARA fail-safe unavailable") from exc


def _audit_rejection(
    event_type: str,
    *,
    actor: str,
    reason_code: str,
    access: VoiceAccessContext | None = None,
    target_user: str | None = None,
) -> None:
    try:
        _voice_store().record_rejection(
            event_type,
            actor=actor,
            reason_code=reason_code,
            tenant_id=access.tenant_id if access is not None else None,
            target_user=target_user or (access.user_uuid if access is not None else None),
        )
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility audit unavailable") from exc


def _account(public_user_id: str):
    account = _identity_store().get_account_by_public_id(public_user_id)
    if account is None or account.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="SARA user not found")
    return account


def _private_json(content: dict) -> JSONResponse:
    return JSONResponse(content=content, headers={"Cache-Control": "private, no-store"})


def _usage_limits(settings: Settings, *, text: str = "") -> VoiceUsageLimits:
    segment_count = len(split_sentences(text)) if text else 1
    synthesis_window = int(settings.voice_timeout_seconds * segment_count) + VOICE_LEASE_GRACE_SECONDS
    return VoiceUsageLimits(
        user_jobs_per_minute=settings.voice_1_1a_user_jobs_per_minute,
        user_jobs_per_day=settings.voice_1_1a_user_jobs_per_day,
        user_characters_per_day=settings.voice_1_1a_user_characters_per_day,
        tenant_jobs_per_minute=settings.voice_1_1a_tenant_jobs_per_minute,
        tenant_jobs_per_day=settings.voice_1_1a_tenant_jobs_per_day,
        tenant_characters_per_day=settings.voice_1_1a_tenant_characters_per_day,
        user_concurrency=settings.voice_1_1a_user_concurrency,
        tenant_concurrency=settings.voice_1_1a_tenant_concurrency,
        lease_seconds=max(settings.voice_1_1a_lease_seconds, synthesis_window),
    )


def _prune_jobs(manager: VoiceJobManager) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=VOICE_JOB_RETENTION_SECONDS)
    expired = [
        job_id
        for job_id, job in manager.jobs.items()
        if datetime.fromisoformat(job.created_at).astimezone(timezone.utc) <= cutoff
    ]
    for job_id in expired:
        manager.jobs.pop(job_id, None)
    overflow = len(manager.jobs) - VOICE_JOB_MAX_ITEMS
    if overflow > 0:
        oldest = sorted(manager.jobs.values(), key=lambda item: item.created_at)[:overflow]
        for job in oldest:
            manager.jobs.pop(job.job_id, None)


def _job_manager(settings: Settings) -> VoiceJobManager | None:
    global _voice_job_manager
    if _voice_job_manager is not None:
        return _voice_job_manager
    if not settings.piper_service_token.strip():
        return None
    voice_client = PiperVoiceClient(
        settings.piper_service_url,
        settings.piper_service_token,
        timeout_seconds=settings.voice_timeout_seconds,
    )
    _voice_job_manager = VoiceJobManager(
        voice_client=voice_client,
        source_commit_sha=os.getenv("SARA_SOURCE_COMMIT_SHA", ""),
        deployment_id=os.getenv("RAILWAY_DEPLOYMENT_ID", ""),
        voice_service_url=settings.piper_service_url,
    )
    return _voice_job_manager


def _owned_job(
    request: Request,
    job_id: str,
) -> tuple[VoiceAccessContext, VoiceAccessibilityStore, VoiceJobManager, object]:
    _, access = _authorized_access(request)
    store = _voice_store()
    try:
        owns_job = store.owns_job(job_id, access)
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility persistence unavailable") from exc
    if not owns_job:
        _audit_rejection(
            "OWNERSHIP_REJECTED",
            actor=access.user_uuid,
            reason_code="job_not_owned",
            access=access,
        )
        raise HTTPException(status_code=404, detail="Voice job not found")
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility configuration unavailable") from exc
    manager = _job_manager(settings)
    if manager is not None:
        _prune_jobs(manager)
    job = manager.get_job(job_id) if manager is not None else None
    if manager is None or job is None:
        _audit_rejection(
            "OWNERSHIP_REJECTED",
            actor=access.user_uuid,
            reason_code="job_unavailable",
            access=access,
        )
        raise HTTPException(status_code=404, detail="Voice job not found")
    return access, store, manager, job


def _rate_limit_http(exc: VoiceRateLimitRejected) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    status_code = 409 if exc.reason_code in {"user_concurrency", "tenant_concurrency"} else 429
    return HTTPException(status_code=status_code, detail=exc.reason_code, headers=headers)


@router.post("/admin/voice-accessibility/entitlements")
async def grant_voice_accessibility_entitlement(request: Request):
    _owner(request)
    try:
        body = VoiceAccessibilityEntitlementRequest.model_validate(await request.json())
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Voice entitlement request rejected") from exc
    account = _account(body.public_user_id)
    actor_hash = hashlib.sha256(b"owner").hexdigest()
    _checkpoint("grant_entitlement", FailSafeEvent.PRE_MUTATION, actor_hash=actor_hash)
    try:
        _voice_store().grant_entitlement(
            account.user_uuid,
            "owner",
            expires_at=body.expires_at,
        )
    except (VoiceAccessRejected, VoiceAccessStoreError) as exc:
        raise HTTPException(status_code=503, detail="Voice entitlement update unavailable") from exc
    return {"public_user_id": account.public_user_id, "status": "ACTIVE", "expires_at": body.expires_at}


@router.get("/admin/voice-accessibility/entitlements/{public_user_id}")
def get_voice_accessibility_entitlement(public_user_id: str, request: Request):
    _owner(request)
    account = _account(public_user_id)
    try:
        summary = _voice_store().entitlement_summary(account.user_uuid)
    except VoiceAccessRejected as exc:
        raise HTTPException(status_code=404, detail="Voice entitlement not found") from exc
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice entitlement read unavailable") from exc
    return {"public_user_id": account.public_user_id, **summary}


@router.post("/admin/voice-accessibility/entitlements/{public_user_id}/revoke")
def revoke_voice_accessibility_entitlement(public_user_id: str, request: Request):
    _owner(request)
    account = _account(public_user_id)
    actor_hash = hashlib.sha256(b"owner").hexdigest()
    _checkpoint("revoke_entitlement", FailSafeEvent.PRE_MUTATION, actor_hash=actor_hash)
    try:
        _voice_store().revoke_entitlement(account.user_uuid, "owner")
    except VoiceAccessRejected as exc:
        raise HTTPException(status_code=404, detail="Voice entitlement not found") from exc
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice entitlement update unavailable") from exc
    return {"public_user_id": account.public_user_id, "status": "REVOKED"}


@router.delete("/admin/voice-accessibility/data/{public_user_id}")
def purge_voice_accessibility_data(public_user_id: str, request: Request):
    _owner(request)
    account = _account(public_user_id)
    actor_hash = hashlib.sha256(b"owner").hexdigest()
    _checkpoint("purge_user_data", FailSafeEvent.PRE_MUTATION, actor_hash=actor_hash)
    try:
        return _voice_store().purge_user_data(account.user_uuid, "owner")
    except VoiceAccessRejected as exc:
        raise HTTPException(status_code=404, detail="Voice membership not found") from exc
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice data purge unavailable") from exc


@router.get("/v1/accessibility/voice/preferences")
def get_voice_accessibility_preferences(request: Request):
    _, access = _authorized_access(request)
    try:
        preferences = _voice_store().get_preferences(access)
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice preferences unavailable") from exc
    return _private_json(
        {
            "speech_rate": preferences.speech_rate,
            "preserve_transcript": preferences.preserve_transcript,
            "transcript_retention_seconds": preferences.transcript_retention_seconds,
        }
    )


@router.put("/v1/accessibility/voice/preferences")
async def put_voice_accessibility_preferences(request: Request):
    principal, access = _authorized_access(request)
    try:
        body = VoiceAccessibilityPreferencesRequest.model_validate(await request.json())
    except (TypeError, ValueError) as exc:
        _audit_rejection(
            "REQUEST_REJECTED",
            actor=principal.public_user_id,
            reason_code="preferences_invalid",
            access=access,
        )
        raise HTTPException(status_code=422, detail="Voice preferences request rejected") from exc
    actor_hash = hashlib.sha256(principal.public_user_id.encode("utf-8")).hexdigest()
    _checkpoint("set_preferences", FailSafeEvent.PRE_MUTATION, actor_hash=actor_hash)
    preferences = VoicePreferences(
        speech_rate=body.speech_rate,
        preserve_transcript=body.preserve_transcript,
        transcript_retention_seconds=body.transcript_retention_seconds,
    )
    try:
        saved = _voice_store().set_preferences(access, preferences)
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice preferences unavailable") from exc
    return _private_json(
        {
            "speech_rate": saved.speech_rate,
            "preserve_transcript": saved.preserve_transcript,
            "transcript_retention_seconds": saved.transcript_retention_seconds,
        }
    )


@router.post("/v1/accessibility/voice/jobs")
async def create_voice_accessibility_job(request: Request):
    settings = _require_release()
    principal = _principal(request)
    _require_voice_scope(principal)
    access = _access(principal)
    try:
        body = VoiceAccessibilityJobRequest.model_validate(await request.json())
    except (TypeError, ValueError) as exc:
        _audit_rejection(
            "REQUEST_REJECTED",
            actor=principal.public_user_id,
            reason_code="job_request_invalid",
            access=access,
        )
        raise HTTPException(status_code=422, detail="Voice accessibility request rejected") from exc
    text = body.text.strip()
    if not text or len(text) > settings.voice_max_characters:
        _audit_rejection(
            "REQUEST_REJECTED",
            actor=principal.public_user_id,
            reason_code="voice_text_rejected",
            access=access,
        )
        raise HTTPException(status_code=422, detail="Voice text rejected")
    manager = _job_manager(settings)
    if manager is None:
        raise HTTPException(status_code=503, detail="Voice synthesis unavailable")
    store = _voice_store()
    try:
        preferences = store.get_preferences(access)
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility persistence unavailable") from exc
    speech_rate = body.speech_rate or preferences.speech_rate
    preserve_transcript = (
        body.preserve_transcript
        if body.preserve_transcript is not None
        else preferences.preserve_transcript
    )
    retention_seconds = preferences.transcript_retention_seconds
    if preserve_transcript and retention_seconds == 0:
        retention_seconds = 900
    try:
        reservation = store.reserve_usage(
            access,
            characters=len(text),
            limits=_usage_limits(settings, text=text),
        )
    except VoiceRateLimitRejected as exc:
        _audit_rejection(
            "RATE_LIMIT_REJECTED",
            actor=principal.public_user_id,
            reason_code=exc.reason_code,
            access=access,
        )
        raise _rate_limit_http(exc) from exc
    actor_hash = hashlib.sha256(principal.public_user_id.encode("utf-8")).hexdigest()
    try:
        _checkpoint("create_job", FailSafeEvent.PRE_DISPATCH, actor_hash=actor_hash)
        try:
            job = manager.create_job(
                text=text,
                speech_rate=speech_rate,
                preserve_transcript=False,
                return_audio="segments",
            )
            _prune_jobs(manager)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Voice accessibility request rejected") from exc
        store.record_job(
            job.job_id,
            access,
            job.source_response_sha256,
            preserve_transcript=preserve_transcript,
        )
        store.record_receipt_envelope(
            job.job_id,
            access,
            [receipt.receipt_id for receipt in job.receipts],
        )
        store.mark_job_status(job.job_id, access, job.status)
        if preserve_transcript and job.status == "completed":
            store.save_transcript(
                job.job_id,
                access,
                text,
                datetime.now(timezone.utc) + timedelta(seconds=retention_seconds),
            )
        if job.status == "failed":
            raise HTTPException(status_code=502, detail="Voice synthesis failed")
        return _private_json(job.public_dict(include_transcript=False))
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility persistence unavailable") from exc
    finally:
        try:
            store.release_lease(reservation.lease_id)
        except VoiceAccessStoreError:
            pass


@router.get("/v1/accessibility/voice/jobs/{job_id}")
def get_voice_accessibility_job(job_id: str, request: Request):
    _, _, _, job = _owned_job(request, job_id)
    return _private_json(job.public_dict(include_transcript=False))


@router.post("/v1/accessibility/voice/jobs/{job_id}/stop")
def stop_voice_accessibility_job(job_id: str, request: Request):
    access, store, manager, _ = _owned_job(request, job_id)
    job = manager.stop_job(job_id)
    try:
        store.mark_job_status(
            job_id,
            access,
            job.status,
            stopped=job.stop_requested_at is not None,
        )
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice job update unavailable") from exc
    return _private_json(job.public_dict(include_transcript=False))


@router.get("/v1/accessibility/voice/jobs/{job_id}/segments/{segment_id}/audio")
def get_voice_accessibility_audio(job_id: str, segment_id: str, request: Request):
    _, _, _, job = _owned_job(request, job_id)
    segment_index = next(
        (index for index, segment in enumerate(job.segments) if segment.segment_id == segment_id),
        None,
    )
    if segment_index is None or segment_index >= len(job.audio_segments):
        raise HTTPException(status_code=404, detail="Voice segment not found")
    return Response(
        content=job.audio_segments[segment_index],
        media_type="audio/wav",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/v1/accessibility/voice/jobs/{job_id}/receipts")
def get_voice_accessibility_receipts(job_id: str, request: Request):
    access, store, _, job = _owned_job(request, job_id)
    try:
        envelope = store.receipt_envelope_digest(job_id, access)
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice receipts unavailable") from exc
    if envelope is None:
        raise HTTPException(status_code=404, detail="Voice receipts not found")
    return _private_json(
        {
            "job_id": job_id,
            "access_envelope_sha256": envelope,
            "receipts": [receipt.public_dict() for receipt in job.receipts],
        }
    )


@router.get("/v1/accessibility/voice/jobs/{job_id}/transcript")
def get_voice_accessibility_transcript(job_id: str, request: Request):
    access, store, _, _ = _owned_job(request, job_id)
    try:
        transcript = store.load_transcript(job_id, access)
    except VoiceAccessStoreError as exc:
        raise HTTPException(status_code=503, detail="Voice transcript unavailable") from exc
    if transcript is None:
        raise HTTPException(status_code=404, detail="Voice transcript not found")
    return _private_json({"transcript": transcript})
