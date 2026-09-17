from __future__ import annotations

import hashlib
import hmac
import os
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from sara_unified.api.schemas import (
    VoiceAccessibilityEntitlementRequest,
    VoiceAccessibilityPreferencesRequest,
)
from sara_unified.config import Settings
from sara_v32_hardening import BackupError, FailSafeEvent, RuntimeFailSafe

from .memory import MemoryKeyError
from .user_identity import IdentityStoreError, OAuthPrincipal, OAuthRejected, UserIdentityStore
from .voice_accessibility import (
    VoiceAccessContext,
    VoiceAccessRejected,
    VoiceAccessStoreError,
    VoiceAccessibilityStore,
    VoicePreferences,
)


router = APIRouter()
FAILSAFE = RuntimeFailSafe.from_env()
VOICE_SCOPE = "sara.voice.accessibility"


def _require_release() -> Settings:
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Voice accessibility configuration unavailable") from exc
    if not (
        settings.voice_1_1_enabled
        and settings.voice_1_1a_enabled
        and settings.voice_accessibility_public_enabled
    ):
        raise HTTPException(status_code=404, detail="Not found")
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
    except OAuthRejected as exc:
        raise HTTPException(status_code=401, detail="SARA OAuth authentication rejected") from exc
    except IdentityStoreError as exc:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable") from exc


def _require_voice_scope(principal: OAuthPrincipal) -> None:
    if VOICE_SCOPE not in frozenset(principal.scope.split()):
        raise HTTPException(status_code=403, detail="Voice accessibility scope rejected")


def _access(principal: OAuthPrincipal) -> VoiceAccessContext:
    try:
        return _voice_store().resolve_access(principal.user_uuid)
    except VoiceAccessRejected as exc:
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
        FAILSAFE.ensure_ready()
        FAILSAFE.checkpoint(
            {"voice_accessibility": {"operation": operation, "actor_hash": actor_hash}},
            event,
            correlation_id=f"voice-1-1a-{uuid.uuid4()}",
            metadata={"gateway": "voice_1_1a", "operation": operation},
        )
    except BackupError as exc:
        raise HTTPException(status_code=503, detail="SARA fail-safe unavailable") from exc


def _account(public_user_id: str):
    account = _identity_store().get_account_by_public_id(public_user_id)
    if account is None or account.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="SARA user not found")
    return account


def _private_json(content: dict) -> JSONResponse:
    return JSONResponse(content=content, headers={"Cache-Control": "private, no-store"})


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
