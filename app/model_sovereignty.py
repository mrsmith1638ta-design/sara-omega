from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator


MODULE_NAME = "sara-model-sovereignty"
MODEL_SOVEREIGNTY_VERSION = "2026-09-17.1"
INVARIANTS = [
    "INV-AI-SELF-01",
    "INV-AI-SELF-02",
    "INV-AI-SELF-03",
    "INV-AI-SELF-04",
    "INV-AI-SELF-05",
]

ModelLifecycleOperation = Literal[
    "TRAIN",
    "FINE_TUNE",
    "MERGE_ADAPTER",
    "WRITE_CHECKPOINT",
    "CHANGE_MODEL_URI",
    "REGISTER_MODEL",
    "PROMOTE_MODEL",
    "SWAP_ENDPOINT",
    "RUNTIME_LOAD",
]

MUTATION_OPERATIONS = {
    "TRAIN",
    "FINE_TUNE",
    "MERGE_ADAPTER",
    "WRITE_CHECKPOINT",
}
DEPLOYMENT_OPERATIONS = {
    "CHANGE_MODEL_URI",
    "REGISTER_MODEL",
    "PROMOTE_MODEL",
    "SWAP_ENDPOINT",
}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utcnow()).isoformat()


def _data_dir() -> Path:
    root = Path(os.getenv("SARA_DATA_DIR", "data")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ModelLifecycleRequest(BaseModel):
    operation: ModelLifecycleOperation
    actor: str = Field(min_length=1, max_length=200)
    target_model_uri: str = Field(min_length=1, max_length=2048)
    model_digest: str | None = Field(default=None, max_length=80)
    dataset_digest: str | None = Field(default=None, max_length=80)
    evidence_id: str | None = Field(default=None, max_length=160)
    requested_by_agent: bool = True

    @field_validator("model_digest", "dataset_digest")
    @classmethod
    def validate_digest(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = value.lower()
        if not DIGEST_RE.fullmatch(normalized):
            raise ValueError("digest must be sha256:<64 lowercase hex chars>")
        return normalized


class ModelDigestApproval(BaseModel):
    model_digest: str = Field(max_length=80)
    approval_id: str = Field(min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$")
    approved_by: str = Field(min_length=3, max_length=200)
    scope: Literal["production_runtime_load", "production_deployment"]
    evidence_id: str | None = Field(default=None, max_length=160)

    @field_validator("model_digest")
    @classmethod
    def validate_model_digest(cls, value: str) -> str:
        normalized = value.lower()
        if not DIGEST_RE.fullmatch(normalized):
            raise ValueError("model_digest must be sha256:<64 lowercase hex chars>")
        return normalized


@dataclass
class ModelSovereigntyStore:
    db_path: Path

    @classmethod
    def from_env(cls) -> "ModelSovereigntyStore":
        return cls(_data_dir() / "sara_model_sovereignty.db")

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS model_authorized_digests(
                    model_digest TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    evidence_id TEXT,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_sovereignty_idempotency(
                    idempotency_key TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _reserve(self, key: str, operation: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        payload_hash = _canonical_hash(payload)
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT operation,payload_hash,result_json FROM model_sovereignty_idempotency WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if row:
                if row["operation"] != operation or row["payload_hash"] != payload_hash:
                    raise ValueError("idempotency_key_reused_with_different_payload")
                return False, json.loads(row["result_json"])
            conn.execute(
                "INSERT INTO model_sovereignty_idempotency(idempotency_key,operation,payload_hash,result_json,created_at) VALUES(?,?,?,?,?)",
                (key, operation, payload_hash, json.dumps({"status": "RESERVED"}), _iso()),
            )
        return True, None

    def _complete(self, key: str, result: dict[str, Any]) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE model_sovereignty_idempotency SET result_json=? WHERE idempotency_key=?",
                (json.dumps(result, sort_keys=True), key),
            )

    def save_approval(self, approval: ModelDigestApproval, idempotency_key: str) -> dict[str, Any]:
        payload = approval.model_dump(mode="json")
        fresh, prior = self._reserve(idempotency_key, "model_digest_approval", payload)
        if not fresh:
            return prior or {"status": "UNKNOWN"}
        payload_hash = _canonical_hash(payload)
        with closing(self._connect()) as conn, conn:
            existing = conn.execute(
                "SELECT payload_hash FROM model_authorized_digests WHERE model_digest=?",
                (approval.model_digest,),
            ).fetchone()
            if existing and existing["payload_hash"] != payload_hash:
                result = {"status": "REJECTED", "reason": "model_digest_conflict", "automatic_retry": False}
                self._complete(idempotency_key, result)
                raise ValueError("model_digest_conflict")
            conn.execute(
                """
                INSERT OR IGNORE INTO model_authorized_digests(
                    model_digest,approval_id,approved_by,scope,evidence_id,payload_hash,created_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    approval.model_digest,
                    approval.approval_id,
                    approval.approved_by,
                    approval.scope,
                    approval.evidence_id,
                    payload_hash,
                    _iso(),
                ),
            )
        result = {
            "status": "ACCEPTED",
            "model_digest": approval.model_digest,
            "approval_id": approval.approval_id,
            "payload_hash": payload_hash,
        }
        self._complete(idempotency_key, result)
        return result

    def authorized_digests(self) -> set[str]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT model_digest FROM model_authorized_digests").fetchall()
        return {row["model_digest"] for row in rows}

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM model_authorized_digests").fetchone()[0])


class ModelSovereigntyService:
    def __init__(self, store: ModelSovereigntyStore | None = None):
        self.store = store or ModelSovereigntyStore.from_env()

    @staticmethod
    def _env_authorized_digests() -> set[str]:
        values = re.split(r"[,;\s]+", os.getenv("SARA_AUTHORIZED_MODEL_DIGESTS", "").strip())
        return {value.lower() for value in values if DIGEST_RE.fullmatch(value.lower())}

    @staticmethod
    def _auth_token() -> str:
        token = os.getenv("SARA_MODEL_SOVEREIGNTY_AUTH_TOKEN", "").strip()
        forbidden_names = (
            "OWNER_TOKEN",
            "GPT_ACTION_TOKEN",
            "TEST_TOKEN",
            "SARA_RAILWAY_CONTROL_AUTH_TOKEN",
            "SARA_SOURCE_CONTROL_AUTH_TOKEN",
            "SARA_DEVICE_CONTROL_AUTH_TOKEN",
            "SARA_ATS_INTELLIGENCE_AUTH_TOKEN",
        )
        forbidden = {os.getenv(name, "").strip() for name in forbidden_names}
        forbidden.discard("")
        if not token or token in forbidden:
            return ""
        return token

    def authorize_mutation(self, authorization: str | None) -> None:
        token = self._auth_token()
        if not token:
            raise HTTPException(503, "model sovereignty mutation authority is not separately configured")
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(403, "model sovereignty mutation authority rejected")

    def authorized_digests(self) -> set[str]:
        return self._env_authorized_digests() | self.store.authorized_digests()

    def evaluate(self, request: ModelLifecycleRequest) -> dict[str, Any]:
        digest = request.model_digest
        known = bool(digest and digest in self.authorized_digests())
        base = {
            "module": MODULE_NAME,
            "version": MODEL_SOVEREIGNTY_VERSION,
            "operation": request.operation,
            "actor": request.actor,
            "target_model_uri": request.target_model_uri,
            "model_digest": digest,
            "invariants": INVARIANTS,
            "training_authority": False,
            "deployment_authority": False,
            "agent_model_lifecycle_authority": False,
            "authorized_digest": known,
            "production_load_allowed": False,
            "containment": {
                "state": "CONTAIN_FREEZE_PRESERVE_EVIDENCE_ROLLBACK",
                "preserve_evidence": True,
                "rollback_required": True,
            },
        }
        if request.operation in MUTATION_OPERATIONS:
            return {
                **base,
                "verdict": "DENY",
                "reason": "BLOCKED_PENDING_MODEL_CHANGE_AUTHORIZATION",
            }
        if request.operation in DEPLOYMENT_OPERATIONS:
            if not known:
                return {
                    **base,
                    "verdict": "DENY",
                    "reason": "BLOCKED_UNTRUSTED_MODEL_DIGEST",
                }
            return {
                **base,
                "verdict": "DENY",
                "reason": "BLOCKED_PENDING_DEPLOYMENT_AUTHORIZATION",
            }
        if request.operation == "RUNTIME_LOAD":
            if not known:
                return {
                    **base,
                    "verdict": "DENY",
                    "reason": "BLOCKED_UNSIGNED_MODEL_ARTIFACT",
                }
            return {
                **base,
                "verdict": "ALLOW",
                "reason": "AUTHORIZED_MODEL_DIGEST",
                "production_load_allowed": True,
                "containment": {"state": "NOT_TRIGGERED", "preserve_evidence": False, "rollback_required": False},
            }
        return {**base, "verdict": "DENY", "reason": "UNKNOWN_MODEL_LIFECYCLE_OPERATION"}

    @staticmethod
    def git_commit() -> str:
        for name in ("RAILWAY_GIT_COMMIT_SHA", "RAILWAY_GIT_COMMIT", "GIT_COMMIT_SHA", "SOURCE_COMMIT_SHA"):
            value = os.getenv(name, "").strip()
            if re.fullmatch(r"[0-9a-fA-F]{7,64}", value):
                return value.lower()
        return "UNVERIFIED"

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "module": MODULE_NAME,
            "version": MODEL_SOVEREIGNTY_VERSION,
            "present": True,
            "invariants": INVARIANTS,
            "immutable_model_weights": True,
            "separate_training_authority": bool(self._auth_token()),
            "model_lifecycle_firewall": True,
            "cryptographic_model_allowlist": True,
            "shared_mutable_model": False,
            "data_admission_gate_required": True,
            "training_tool_isolation_required": True,
            "tripwire_response": "CONTAIN_FREEZE_PRESERVE_EVIDENCE_ROLLBACK",
            "agent_model_lifecycle_authority": False,
            "execution_authority": False,
            "deployment_authority": False,
            "authorized_digest_count": len(self.authorized_digests()),
            "stored_authorized_digest_count": self.store.count(),
            "git_commit": self.git_commit(),
        }


_service_instance: ModelSovereigntyService | None = None


def get_service() -> ModelSovereigntyService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ModelSovereigntyService()
    return _service_instance


router = APIRouter(prefix="/model-sovereignty", tags=["Model Sovereignty"])


@router.get("/health")
def model_sovereignty_health():
    return get_service().health()


@router.get("/attestation")
def model_sovereignty_attestation():
    h = get_service().health()
    return {
        "module": h["module"],
        "version": h["version"],
        "git_commit": h["git_commit"],
        "invariants": h["invariants"],
        "agent_model_lifecycle_authority": False,
        "deployment_authority": False,
        "execution_authority": False,
        "cryptographic_model_allowlist": h["cryptographic_model_allowlist"],
        "tripwire_response": h["tripwire_response"],
    }


@router.post("/evaluate")
def model_sovereignty_evaluate(payload: ModelLifecycleRequest):
    return get_service().evaluate(payload)


@router.post("/authorized-digests")
def authorize_model_digest(
    payload: ModelDigestApproval,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    current = get_service()
    current.authorize_mutation(authorization)
    if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(400, "valid Idempotency-Key required")
    try:
        return current.store.save_approval(payload, idempotency_key)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
