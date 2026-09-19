from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator


MODULE_NAME = "sara-enterprise-governance"
ENTERPRISE_GOVERNANCE_VERSION = "2026-09-17.1"


class RoadEvidenceState(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ControlOwner(str, Enum):
    PROVIDER = "PROVIDER"
    SARA = "SARA"
    CLIENT = "CLIENT"
    SHARED = "SHARED"
    THIRD_PARTY = "THIRD_PARTY"


class InheritanceDisposition(str, Enum):
    INHERITABLE = "INHERITABLE"
    SHARED = "SHARED"
    SARA_OWNED = "SARA_OWNED"
    CLIENT_OWNED = "CLIENT_OWNED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ExecutionDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class OperationalStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    CONDITIONALLY_ELIGIBLE = "CONDITIONALLY_ELIGIBLE"
    DISABLED = "DISABLED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNVERIFIED = "UNVERIFIED"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utcnow()).isoformat()


def _data_dir() -> Path:
    root = Path(os.getenv("SARA_DATA_DIR", "data")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9._:/+-]+", " ", (value or "").casefold()).strip()


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"OWNER_TOKEN\s*=\s*[^,\s]+", re.IGNORECASE),
    re.compile(r"admin\s+key", re.IGNORECASE),
    re.compile(r"api[_ -]?key\s*[:=]\s*[^,\s]+", re.IGNORECASE),
]


def _redact(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class AssuranceArtifact(BaseModel):
    artifact_id: str = Field(min_length=3, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=160)
    provider_id: str = Field(min_length=1, max_length=160)
    artifact_type: str = Field(min_length=1, max_length=160)
    source_uri: str = Field(min_length=1, max_length=2048)
    evidence_hash: str = Field(min_length=16, max_length=160)
    effective_from: datetime
    expires_at: datetime | None = None
    scope_text: str = Field(min_length=1, max_length=4000)
    exclusions: list[str] = Field(default_factory=list)
    evidence_state: RoadEvidenceState


class FeatureEligibilityRecord(BaseModel):
    record_id: str = Field(min_length=3, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=160)
    provider_id: str = Field(min_length=1, max_length=160)
    product: str = Field(min_length=1, max_length=200)
    plan: str = Field(min_length=1, max_length=200)
    feature: str = Field(min_length=1, max_length=200)
    region: str | None = Field(default=None, max_length=80)
    required_configuration: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_state: RoadEvidenceState
    operational_status: OperationalStatus = OperationalStatus.UNVERIFIED
    effective_from: datetime
    expires_at: datetime | None = None
    exclusions: list[str] = Field(default_factory=list)


class ControlInheritanceRecord(BaseModel):
    record_id: str = Field(min_length=3, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=160)
    control_id: str = Field(min_length=1, max_length=200)
    provider_id: str = Field(min_length=1, max_length=160)
    product: str = Field(min_length=1, max_length=200)
    plan: str = Field(min_length=1, max_length=200)
    feature: str | None = Field(default=None, max_length=200)
    owner: ControlOwner
    disposition: InheritanceDisposition
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_state: RoadEvidenceState
    exclusions: list[str] = Field(default_factory=list)
    reviewed_at: datetime
    next_review_at: datetime


class GovernanceEvaluationRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=160)
    provider_id: str = Field(min_length=1, max_length=160)
    product: str = Field(min_length=1, max_length=200)
    plan: str = Field(min_length=1, max_length=200)
    feature: str = Field(min_length=1, max_length=200)
    region: str | None = Field(default=None, max_length=80)
    requested_action: str = Field(min_length=1, max_length=240)
    actor_scopes: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    human_approval_id: str | None = Field(default=None, max_length=160)

    @field_validator("actor_scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        return [scope.strip() for scope in value if scope.strip()]


class PassportCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=160)
    release_identity: str = Field(min_length=1, max_length=240)
    source_commit: str = Field(min_length=7, max_length=64)
    decision_ids: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=4000)


@dataclass
class EnterpriseGovernanceStore:
    db_path: str

    @classmethod
    def from_env(cls) -> "EnterpriseGovernanceStore":
        return cls(str(_data_dir() / "sara_enterprise_governance.db"))

    @classmethod
    def in_memory(cls) -> "EnterpriseGovernanceStore":
        return cls(":memory:")

    def __post_init__(self) -> None:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._memory_conn: sqlite3.Connection | None = None
        self._init()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:")
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        if self.db_path != ":memory:":
            conn.close()

    def _init(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS governance_feature_eligibility(
                    tenant_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, record_id)
                );
                CREATE TABLE IF NOT EXISTS governance_control_inheritance(
                    tenant_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, record_id)
                );
                CREATE TABLE IF NOT EXISTS governance_policy_decisions(
                    tenant_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, record_id)
                );
                CREATE TABLE IF NOT EXISTS governance_audit_passports(
                    tenant_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, record_id)
                );
                CREATE TABLE IF NOT EXISTS governance_idempotency(
                    idempotency_key TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            self._close(conn)

    def _upsert(self, table: str, tenant_id: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = _sha256(payload)
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    f"""
                    INSERT INTO {table}(tenant_id,record_id,payload_json,payload_hash,created_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(tenant_id, record_id)
                    DO UPDATE SET payload_json=excluded.payload_json,payload_hash=excluded.payload_hash
                    """,
                    (tenant_id, record_id, payload_json, payload_hash, _iso()),
                )
        finally:
            self._close(conn)
        return {"status": "ACCEPTED", "record_id": record_id, "payload_hash": payload_hash}

    def upsert_feature(self, record: FeatureEligibilityRecord) -> dict[str, Any]:
        return self._upsert(
            "governance_feature_eligibility",
            record.tenant_id,
            record.record_id,
            record.model_dump(mode="json"),
        )

    def upsert_control(self, record: ControlInheritanceRecord) -> dict[str, Any]:
        return self._upsert(
            "governance_control_inheritance",
            record.tenant_id,
            record.record_id,
            record.model_dump(mode="json"),
        )

    def _rows(self, table: str, tenant_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(f"SELECT payload_json FROM {table} WHERE tenant_id=?", (tenant_id,)).fetchall()
        finally:
            self._close(conn)
        return [json.loads(row["payload_json"]) for row in rows]

    def features(self, tenant_id: str) -> list[FeatureEligibilityRecord]:
        return [FeatureEligibilityRecord(**item) for item in self._rows("governance_feature_eligibility", tenant_id)]

    def controls(self, tenant_id: str) -> list[ControlInheritanceRecord]:
        return [ControlInheritanceRecord(**item) for item in self._rows("governance_control_inheritance", tenant_id)]

    def save_decision(self, tenant_id: str, decision: dict[str, Any]) -> None:
        self._upsert("governance_policy_decisions", tenant_id, decision["decision_id"], decision)

    def get_decisions(self, tenant_id: str, decision_ids: list[str]) -> list[dict[str, Any]]:
        if not decision_ids:
            return []
        conn = self._connect()
        try:
            placeholders = ",".join("?" for _ in decision_ids)
            rows = conn.execute(
                f"SELECT payload_json FROM governance_policy_decisions WHERE tenant_id=? AND record_id IN ({placeholders})",
                (tenant_id, *decision_ids),
            ).fetchall()
        finally:
            self._close(conn)
        return [json.loads(row["payload_json"]) for row in rows]

    def save_passport(self, tenant_id: str, passport: dict[str, Any]) -> None:
        self._upsert("governance_audit_passports", tenant_id, passport["passport_id"], passport)

    def get_passport(self, passport_id: str, tenant_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT payload_json FROM governance_audit_passports WHERE tenant_id=? AND record_id=?",
                (tenant_id, passport_id),
            ).fetchone()
        finally:
            self._close(conn)
        return json.loads(row["payload_json"]) if row else None

    def reserve(self, key: str, operation: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        payload_hash = _sha256(payload)
        conn = self._connect()
        try:
            with conn:
                row = conn.execute(
                    "SELECT operation,payload_hash,result_json FROM governance_idempotency WHERE idempotency_key=?",
                    (key,),
                ).fetchone()
                if row:
                    if row["operation"] != operation or row["payload_hash"] != payload_hash:
                        raise ValueError("idempotency_key_reused_with_different_payload")
                    return False, json.loads(row["result_json"])
                conn.execute(
                    "INSERT INTO governance_idempotency(idempotency_key,operation,payload_hash,result_json,created_at) VALUES(?,?,?,?,?)",
                    (key, operation, payload_hash, json.dumps({"status": "RESERVED"}), _iso()),
                )
        finally:
            self._close(conn)
        return True, None

    def complete(self, key: str, result: dict[str, Any]) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE governance_idempotency SET result_json=? WHERE idempotency_key=?",
                    (json.dumps(result, sort_keys=True, default=str), key),
                )
        finally:
            self._close(conn)

    def counts(self) -> dict[str, int]:
        conn = self._connect()
        try:
            return {
                "features": int(conn.execute("SELECT COUNT(*) FROM governance_feature_eligibility").fetchone()[0]),
                "controls": int(conn.execute("SELECT COUNT(*) FROM governance_control_inheritance").fetchone()[0]),
                "decisions": int(conn.execute("SELECT COUNT(*) FROM governance_policy_decisions").fetchone()[0]),
                "passports": int(conn.execute("SELECT COUNT(*) FROM governance_audit_passports").fetchone()[0]),
            }
        finally:
            self._close(conn)


class EnterpriseGovernanceService:
    def __init__(self, store: EnterpriseGovernanceStore | None = None):
        self.store = store or EnterpriseGovernanceStore.from_env()

    @staticmethod
    def _auth_token() -> str:
        token = os.getenv("SARA_ENTERPRISE_GOVERNANCE_ADMIN_TOKEN", "").strip()
        forbidden_names = (
            "OWNER_TOKEN",
            "GPT_ACTION_TOKEN",
            "TEST_TOKEN",
            "SARA_MODEL_SOVEREIGNTY_AUTH_TOKEN",
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

    def authorize_admin(self, authorization: str | None) -> None:
        token = self._auth_token()
        if not token:
            raise HTTPException(503, "enterprise governance admin authority is not separately configured")
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(403, "enterprise governance admin authority rejected")

    @staticmethod
    def required_scopes(requested_action: str) -> set[str]:
        if requested_action.startswith("governance_get_"):
            return {"sara.governance.read"}
        if requested_action in {"governance_create_audit_passport", "governance_update_policy"}:
            return {"sara.governance.admin"}
        return {"sara.governance.evaluate"}

    @staticmethod
    def requires_human_approval(requested_action: str) -> bool:
        return requested_action in {
            "governance_create_audit_passport",
            "governance_update_policy",
            "provider_evidence_mutation",
            "control_ownership_mutation",
        }

    @staticmethod
    def _matches_feature(item: FeatureEligibilityRecord, request: GovernanceEvaluationRequest) -> bool:
        return (
            item.tenant_id == request.tenant_id
            and _normalize(item.provider_id) == _normalize(request.provider_id)
            and _normalize(item.product) == _normalize(request.product)
            and _normalize(item.plan) == _normalize(request.plan)
            and _normalize(item.feature) == _normalize(request.feature)
            and _normalize(item.region) == _normalize(request.region)
        )

    @staticmethod
    def _matches_control(item: ControlInheritanceRecord, request: GovernanceEvaluationRequest) -> bool:
        return (
            item.tenant_id == request.tenant_id
            and _normalize(item.provider_id) == _normalize(request.provider_id)
            and _normalize(item.product) == _normalize(request.product)
            and _normalize(item.plan) == _normalize(request.plan)
            and (item.feature is None or _normalize(item.feature) == _normalize(request.feature))
        )

    @staticmethod
    def _config_missing(feature: FeatureEligibilityRecord, request: GovernanceEvaluationRequest) -> list[str]:
        missing = []
        for key, expected in feature.required_configuration.items():
            if request.configuration.get(key) != expected:
                missing.append(str(key))
        return missing

    def evaluate(self, request: GovernanceEvaluationRequest, now: datetime | None = None) -> dict[str, Any]:
        now = now or _utcnow()
        reasons: list[str] = []
        feature = next((item for item in self.store.features(request.tenant_id) if self._matches_feature(item, request)), None)
        control = next((item for item in self.store.controls(request.tenant_id) if self._matches_control(item, request)), None)
        evidence_state = RoadEvidenceState.UNVERIFIED
        decision = ExecutionDecision.DENY

        if feature is None:
            reasons.append("FEATURE_NOT_REGISTERED")
        else:
            evidence_state = feature.evidence_state
            if feature.evidence_state != RoadEvidenceState.PASS:
                reasons.append("FEATURE_EVIDENCE_NOT_PASS")
            if feature.operational_status not in {OperationalStatus.ELIGIBLE, OperationalStatus.CONDITIONALLY_ELIGIBLE}:
                reasons.append("FEATURE_OPERATIONALLY_NOT_ELIGIBLE")
            if feature.expires_at and feature.expires_at <= now:
                reasons.append("FEATURE_EVIDENCE_STALE")
            if any(_normalize(exclusion) and _normalize(exclusion) in _normalize(request.requested_action) for exclusion in feature.exclusions):
                reasons.append("FEATURE_EXCLUSION_APPLIES")
            missing_config = self._config_missing(feature, request)
            if missing_config:
                reasons.append("REQUIRED_CONFIGURATION_MISSING:" + ",".join(sorted(missing_config)))

        if not reasons:
            if control is None:
                reasons.append("CONTROL_OWNERSHIP_UNRESOLVED")
            else:
                evidence_state = control.evidence_state
                if control.evidence_state != RoadEvidenceState.PASS:
                    reasons.append("CONTROL_EVIDENCE_NOT_PASS")
                if control.next_review_at <= now:
                    reasons.append("CONTROL_EVIDENCE_STALE")
                if control.disposition == InheritanceDisposition.OUT_OF_SCOPE:
                    reasons.append("CONTROL_OUT_OF_SCOPE")
                if any(_normalize(exclusion) and _normalize(exclusion) in _normalize(request.requested_action) for exclusion in control.exclusions):
                    reasons.append("CONTROL_EXCLUSION_APPLIES")

        if not reasons:
            required = self.required_scopes(request.requested_action)
            if not required.issubset(set(request.actor_scopes)):
                reasons.append("INSUFFICIENT_SCOPE")

        if not reasons and self.requires_human_approval(request.requested_action) and not request.human_approval_id:
            decision = ExecutionDecision.REQUIRE_APPROVAL
            reasons.append("HUMAN_APPROVAL_REQUIRED")
        elif not reasons:
            decision = ExecutionDecision.ALLOW
            reasons.append("GOVERNED_EXECUTION_ALLOWED")

        payload = {
            "module": MODULE_NAME,
            "version": ENTERPRISE_GOVERNANCE_VERSION,
            "decision_id": f"gov-{uuid.uuid4()}",
            "tenant_id": request.tenant_id,
            "actor_id_hash": hashlib.sha256(request.actor_id.encode("utf-8")).hexdigest(),
            "provider_id": request.provider_id,
            "product": request.product,
            "plan": request.plan,
            "feature": request.feature,
            "region": request.region,
            "requested_action": request.requested_action,
            "required_scopes": sorted(self.required_scopes(request.requested_action)),
            "evidence_state": evidence_state.value,
            "decision": decision.value,
            "reasons": reasons,
            "feature_record_id": feature.record_id if feature else None,
            "control_record_id": control.record_id if control else None,
            "independent_assurance": False,
            "audit_opinion": False,
            "certification_statement": False,
            "created_at": _iso(now),
        }
        payload["evidence_hash"] = _sha256(payload)
        self.store.save_decision(request.tenant_id, payload)
        return payload

    def create_audit_passport(
        self,
        *,
        tenant_id: str,
        release_identity: str,
        source_commit: str,
        decision_ids: list[str],
        notes: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or _utcnow()
        decisions = self.store.get_decisions(tenant_id, decision_ids)
        features = [item.model_dump(mode="json") for item in self.store.features(tenant_id)]
        controls = [item.model_dump(mode="json") for item in self.store.controls(tenant_id)]
        passport = {
            "module": MODULE_NAME,
            "version": ENTERPRISE_GOVERNANCE_VERSION,
            "passport_id": f"passport-{uuid.uuid4()}",
            "tenant_id": tenant_id,
            "release_identity": release_identity,
            "source_commit": source_commit,
            "feature_eligibility_snapshot": features,
            "control_ownership_matrix": controls,
            "policy_decisions": decisions,
            "notes": _redact(notes),
            "independent_assurance": False,
            "audit_opinion": False,
            "certification_statement": False,
            "generated_at": _iso(now),
        }
        passport["evidence_hash"] = _sha256(passport)
        self.store.save_passport(tenant_id, passport)
        return passport

    def get_audit_passport(self, passport_id: str, tenant_id: str) -> dict[str, Any] | None:
        return self.store.get_passport(passport_id, tenant_id)

    def save_feature(self, record: FeatureEligibilityRecord, idempotency_key: str) -> dict[str, Any]:
        payload = record.model_dump(mode="json")
        fresh, prior = self.store.reserve(idempotency_key, "feature_eligibility", payload)
        if not fresh:
            return prior or {"status": "UNKNOWN"}
        result = self.store.upsert_feature(record)
        self.store.complete(idempotency_key, result)
        return result

    def save_control(self, record: ControlInheritanceRecord, idempotency_key: str) -> dict[str, Any]:
        payload = record.model_dump(mode="json")
        fresh, prior = self.store.reserve(idempotency_key, "control_inheritance", payload)
        if not fresh:
            return prior or {"status": "UNKNOWN"}
        result = self.store.upsert_control(record)
        self.store.complete(idempotency_key, result)
        return result

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
            "version": ENTERPRISE_GOVERNANCE_VERSION,
            "present": True,
            "road_evidence_states": [item.value for item in RoadEvidenceState],
            "operational_statuses": [item.value for item in OperationalStatus],
            "oauth_scopes": [
                "sara.solve",
                "sara.memory",
                "sara.governance.read",
                "sara.governance.evaluate",
                "sara.governance.admin",
            ],
            "admin_authority_separate": bool(self._auth_token()),
            "authentication_is_not_execution_authority": True,
            "provider_certification_is_not_sara_certification": True,
            "missing_evidence_fails_closed": True,
            "audit_passport_is_not_audit_opinion": True,
            "secret_redaction": True,
            "counts": self.store.counts(),
            "git_commit": self.git_commit(),
        }


_service_instance: EnterpriseGovernanceService | None = None


def get_service() -> EnterpriseGovernanceService:
    global _service_instance
    if _service_instance is None:
        _service_instance = EnterpriseGovernanceService()
    return _service_instance


router = APIRouter(prefix="/enterprise-governance", tags=["Enterprise Governance"])


@router.get("/health")
def governance_health():
    return get_service().health()


@router.post("/feature-eligibility")
def governance_feature_eligibility(
    payload: FeatureEligibilityRecord,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    service = get_service()
    service.authorize_admin(authorization)
    if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(400, "valid Idempotency-Key required")
    try:
        return service.save_feature(payload, idempotency_key)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/control-inheritance")
def governance_control_inheritance(
    payload: ControlInheritanceRecord,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    service = get_service()
    service.authorize_admin(authorization)
    if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(400, "valid Idempotency-Key required")
    try:
        return service.save_control(payload, idempotency_key)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/evaluate-action")
def governance_evaluate_action(payload: GovernanceEvaluationRequest):
    return get_service().evaluate(payload)


@router.get("/control-matrix/{tenant_id}")
def governance_get_control_matrix(tenant_id: str):
    service = get_service()
    return {
        "tenant_id": tenant_id,
        "features": [item.model_dump(mode="json") for item in service.store.features(tenant_id)],
        "controls": [item.model_dump(mode="json") for item in service.store.controls(tenant_id)],
    }


@router.post("/audit-passports")
def governance_create_audit_passport(
    payload: PassportCreateRequest,
    authorization: str | None = Header(default=None),
):
    service = get_service()
    service.authorize_admin(authorization)
    return service.create_audit_passport(**payload.model_dump(mode="python"))


@router.get("/audit-passports/{tenant_id}/{passport_id}")
def governance_get_audit_passport(tenant_id: str, passport_id: str):
    passport = get_service().get_audit_passport(passport_id, tenant_id)
    if passport is None:
        raise HTTPException(404, "audit passport not found")
    return passport
