from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from sara_v32_hardening import BackupError, FailSafeEvent, RuntimeFailSafe

from .memory import ConversationMemory, MemoryKeyError, MemoryStoreError
from .models import Problem
from .orchestrator import SaraOmega
from .user_identity import IdentityStoreError, OAuthPrincipal, OAuthRejected, UserIdentityStore


router = APIRouter()
GATEWAY_SARA = SaraOmega()
FAILSAFE = RuntimeFailSafe.from_env()

UserGatewayOperation = Literal["solve", "memory_status", "memory_recall", "memory_forget"]


class UserGatewayRequest(BaseModel):
    operation: UserGatewayOperation
    query: str | None = Field(default=None, max_length=5000)
    objective: str | None = Field(default=None, max_length=2000)
    requested_action: str | None = Field(default=None, max_length=1000)
    context: dict[str, Any] = Field(default_factory=dict)
    council: bool | None = None
    session_id: str | None = Field(default=None, max_length=256)


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


def _memory() -> ConversationMemory:
    try:
        memory = ConversationMemory.from_env(required=True)
    except (MemoryKeyError, MemoryStoreError) as exc:
        raise HTTPException(status_code=503, detail="SARA encrypted memory unavailable") from exc
    if memory is None:
        raise HTTPException(status_code=503, detail="SARA encrypted memory unavailable")
    return memory


def _principal(request: Request) -> OAuthPrincipal:
    token = _bearer(request)
    try:
        return _identity_store().resolve_access_token(token)
    except OAuthRejected as exc:
        raise HTTPException(status_code=401, detail="SARA OAuth authentication rejected") from exc
    except IdentityStoreError as exc:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable") from exc


def _require_scope(principal: OAuthPrincipal, required_scope: str) -> None:
    scopes = frozenset(item for item in principal.scope.split() if item)
    if required_scope not in scopes:
        raise HTTPException(status_code=403, detail="SARA OAuth scope rejected")


def _ensure_failsafe() -> None:
    try:
        FAILSAFE.ensure_ready()
    except BackupError as exc:
        raise HTTPException(status_code=503, detail="SARA fail-safe unavailable") from exc


def _checkpoint(principal: OAuthPrincipal, operation: str, event: FailSafeEvent) -> None:
    try:
        FAILSAFE.checkpoint(
            {
                "user_memory": {
                    "operation": operation,
                    "public_user_id": principal.public_user_id,
                }
            },
            event,
            correlation_id=f"user-memory-{uuid.uuid4()}",
            metadata={"gateway": "sara_oauth_user", "operation": operation},
        )
    except BackupError as exc:
        raise HTTPException(status_code=503, detail="SARA fail-safe checkpoint unavailable") from exc


def _verdict_payload(verdict: Any) -> dict[str, Any]:
    if hasattr(verdict, "model_dump"):
        value = verdict.model_dump()
        if isinstance(value, dict):
            return value
    if isinstance(verdict, dict):
        return verdict
    return {
        "decision": str(getattr(verdict, "decision", ""))[:2000],
        "why": str(getattr(verdict, "why", ""))[:4000],
        "confidence": getattr(verdict, "confidence", None),
        "decision_id": str(getattr(verdict, "decision_id", ""))[:256],
    }


def _assistant_memory(verdict: Any) -> str:
    decision = str(getattr(verdict, "decision", "") or "").strip()
    why = str(getattr(verdict, "why", "") or "").strip()
    combined = decision if not why else f"{decision}\n{why}" if decision else why
    return combined[:4000]


@router.post("/gpt/user/gateway")
async def sara_user_gateway(request: Request, body: UserGatewayRequest):
    principal = _principal(request)
    _ensure_failsafe()
    memory = _memory()

    if body.operation == "memory_status":
        _require_scope(principal, "sara.memory")
        continuity = memory.load_user_continuity(principal.user_uuid)
        return {
            "service": "sara-oauth-user-gateway",
            "operation": "memory_status",
            "public_user_id": principal.public_user_id,
            "thread_count": continuity["thread_count"],
        }

    if body.operation == "memory_recall":
        _require_scope(principal, "sara.memory")
        return {
            "service": "sara-oauth-user-gateway",
            "operation": "memory_recall",
            "public_user_id": principal.public_user_id,
            "continuity": memory.load_user_continuity(principal.user_uuid),
        }

    if body.operation == "memory_forget":
        _require_scope(principal, "sara.memory")
        if body.context.get("confirm") is not True:
            raise HTTPException(status_code=400, detail="Explicit memory-forget confirmation required")
        _checkpoint(principal, body.operation, FailSafeEvent.PRE_MUTATION)
        memory.forget_user(principal.user_uuid)
        return {
            "service": "sara-oauth-user-gateway",
            "operation": "memory_forget",
            "public_user_id": principal.public_user_id,
            "forgotten": True,
        }

    _require_scope(principal, "sara.solve")
    query = (body.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required for solve")
    session_id = body.session_id or str(uuid.uuid4())
    try:
        thread_history = memory.load_for_user(principal.user_uuid, session_id)
        continuity = memory.load_user_continuity(principal.user_uuid)
    except MemoryStoreError as exc:
        raise HTTPException(status_code=503, detail="SARA encrypted memory read failed") from exc

    problem_context = dict(body.context)
    problem_context.pop("confirm", None)
    problem_context["source"] = "sara_oauth_user_gateway"
    problem_context["sara_user_continuity"] = continuity
    problem_context["sara_thread_history"] = thread_history[-50:]
    problem = Problem(
        query=query,
        objective=body.objective,
        requested_action=body.requested_action,
        context=problem_context,
        council=body.council,
        actor="sara_oauth_user",
        authority_level=1,
    )

    _checkpoint(principal, body.operation, FailSafeEvent.PRE_DISPATCH)
    verdict = await GATEWAY_SARA.solve(problem)
    assistant_content = _assistant_memory(verdict)
    updated_messages = [
        *thread_history,
        {"role": "user", "content": query[:5000]},
        {"role": "assistant", "content": assistant_content},
    ]
    _checkpoint(principal, body.operation, FailSafeEvent.PRE_MUTATION)
    try:
        memory.save_for_user(principal.user_uuid, session_id, updated_messages)
        memory.update_user_continuity(
            principal.user_uuid,
            session_id=session_id,
            messages=updated_messages,
        )
    except MemoryStoreError as exc:
        raise HTTPException(status_code=503, detail="SARA encrypted memory write failed") from exc

    return {
        "service": "sara-oauth-user-gateway",
        "operation": "solve",
        "public_user_id": principal.public_user_id,
        "session_id": session_id,
        "verdict": _verdict_payload(verdict),
    }
