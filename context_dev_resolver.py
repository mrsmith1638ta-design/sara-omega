"""Fail-closed Context.dev commercial authorization boundary for SARA-OMEGA.

This module intentionally contains no Context.dev credentials or HTTP vendor
transport. Commercial authorization is loaded only from reviewed, hash-bound
repository evidence and fails closed to UNVERIFIED if that evidence is missing,
malformed, or changed without an updated approval record.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

POLICY_ID = "CTX-COMMERCIAL-RESOLVER-001"
VENDOR = "Context Dev Inc."
SERVICE = "Context.dev"
TERMS_VERSION_REVIEWED = "2026-08-20"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
REPO_ROOT = Path(__file__).resolve().parent
AUTHORIZATION_STATE_PATH = REPO_ROOT / "Context.Dev" / "evidence" / "authorization-state.json"


class AuthorizationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    PENDING_WRITTEN_AUTHORIZATION = "PENDING_WRITTEN_AUTHORIZATION"
    VERIFIED = "VERIFIED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    SUSPENDED = "SUSPENDED"


class EpistemicClassification(str, Enum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    INFERRED = "INFERRED"
    DISPUTED = "DISPUTED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"
    CURRENTLY_INACCESSIBLE = "CURRENTLY_INACCESSIBLE"


class ApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ChangeStream(str, Enum):
    LEGAL_LICENSE = "LEGAL_LICENSE"
    TECHNICAL_API = "TECHNICAL_API"


class DenialCode(str, Enum):
    COMMERCIAL_AUTHORIZATION_NOT_VERIFIED = "COMMERCIAL_AUTHORIZATION_NOT_VERIFIED"
    TERMS_HASH_MISSING = "TERMS_HASH_MISSING"
    TERMS_HASH_MISMATCH = "TERMS_HASH_MISMATCH"
    AUTOMATED_USE_NOT_AUTHORIZED = "AUTOMATED_USE_NOT_AUTHORIZED"
    SCOPE_NOT_AUTHORIZED = "SCOPE_NOT_AUTHORIZED"
    TARGET_SITE_RIGHTS_FAILED = "TARGET_SITE_RIGHTS_FAILED"
    ZDR_NOT_VERIFIED = "ZDR_NOT_VERIFIED"


REQUIRED_COMMERCIAL_SCOPES = frozenset(
    {
        "commercial_saas",
        "automated_api_use",
        "agent_mcp_use",
        "end_user_triggered_requests",
        "derived_outputs",
        "source_citations",
        "evidence_retention",
        "reasonable_caching",
        "monitoring",
        "commercial_subscription_revenue",
    }
)

MATERIAL_LEGAL_TOPICS = frozenset(
    {
        "commercial rights",
        "automation",
        "ai agents",
        "retention",
        "intellectual property",
        "downstream distribution",
        "privacy",
        "termination",
        "indemnification",
        "authorization",
    }
)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_sha256(value: str | None) -> bool:
    return bool(value and SHA256_RE.fullmatch(value))


@dataclass(frozen=True)
class EvidenceLedgerEntry:
    vendor: str
    source_url: str
    document_title: str
    retrieved_at: str
    effective_date: str | None
    terms_version: str
    sha256_content_hash: str
    claim: str
    evidence_excerpt_reference: str
    epistemic_classification: EpistemicClassification
    authorization_scope: tuple[str, ...]
    superseded_by: str | None
    reviewer: str
    approval_state: ApprovalState

    def validation_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        for field_name in (
            "vendor",
            "source_url",
            "document_title",
            "terms_version",
            "claim",
            "evidence_excerpt_reference",
            "reviewer",
        ):
            if not str(getattr(self, field_name)).strip():
                errors.append(f"{field_name} is required")
        try:
            datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        except ValueError:
            errors.append("retrieved_at must be ISO-8601 compatible")
        if not is_sha256(self.sha256_content_hash):
            errors.append("sha256_content_hash must be a lowercase SHA-256 digest")
        if not self.authorization_scope:
            errors.append("authorization_scope must not be empty")
        return tuple(errors)


@dataclass(frozen=True)
class VendorLicenseState:
    authorization_state: AuthorizationState
    authorized_scopes: frozenset[str]
    stored_terms_hash: str | None
    verified_terms_hash: str | None
    terms_version: str
    reviewed_at: str | None
    evidence: tuple[EvidenceLedgerEntry, ...] = ()
    vendor: str = VENDOR
    service: str = SERVICE

    @classmethod
    def pending_msa(cls) -> VendorLicenseState:
        return cls(
            authorization_state=AuthorizationState.PENDING_WRITTEN_AUTHORIZATION,
            authorized_scopes=frozenset(),
            stored_terms_hash=None,
            verified_terms_hash=None,
            terms_version=TERMS_VERSION_REVIEWED,
            reviewed_at=None,
            evidence=(),
        )

    def has_approved_evidence(self, scope: str) -> bool:
        return any(
            entry.approval_state is ApprovalState.APPROVED
            and entry.epistemic_classification is EpistemicClassification.VERIFIED
            and entry.superseded_by is None
            and scope in entry.authorization_scope
            and not entry.validation_errors()
            for entry in self.evidence
        )

    def commercial_runtime_authorized(self) -> bool:
        return bool(
            self.authorization_state is AuthorizationState.VERIFIED
            and is_sha256(self.stored_terms_hash)
            and self.stored_terms_hash == self.verified_terms_hash
            and REQUIRED_COMMERCIAL_SCOPES.issubset(self.authorized_scopes)
            and all(
                self.has_approved_evidence(scope)
                for scope in REQUIRED_COMMERCIAL_SCOPES
            )
        )

    def public_status(self) -> dict[str, Any]:
        commercial_runtime_authorized = self.commercial_runtime_authorized()
        return {
            "vendor": self.vendor,
            "service": self.service,
            "policy_id": POLICY_ID,
            "terms_version_reviewed": self.terms_version,
            "commercial_authorization": self.authorization_state.value,
            "monetized_runtime": "ALLOWED"
            if commercial_runtime_authorized
            else "BLOCKED",
            "fail_mode": "CLOSED",
            "credentials_configured": False,
            "vendor_transport_enabled": False,
            "production_authorization": "SCOPE_VERIFIED"
            if commercial_runtime_authorized
            else "BLOCKED",
        }


def _unverified_license() -> VendorLicenseState:
    return VendorLicenseState(
        authorization_state=AuthorizationState.UNVERIFIED,
        authorized_scopes=frozenset(),
        stored_terms_hash=None,
        verified_terms_hash=None,
        terms_version=TERMS_VERSION_REVIEWED,
        reviewed_at=None,
        evidence=(),
    )


def _repository_evidence_path(relative_path: str) -> Path:
    candidate = (REPO_ROOT / relative_path).resolve()
    candidate.relative_to(REPO_ROOT)
    return candidate


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_context_dev_license(
    state_path: Path = AUTHORIZATION_STATE_PATH,
) -> VendorLicenseState:
    """Load reviewed Context.dev authorization evidence; any defect fails closed."""
    try:
        record = json.loads(state_path.read_text(encoding="utf-8"))
        if record.get("schema_version") != 1:
            return _unverified_license()
        if record.get("policy_id") != POLICY_ID:
            return _unverified_license()
        if record.get("vendor") != VENDOR or record.get("service") != SERVICE:
            return _unverified_license()
        if record.get("authorization_state") != AuthorizationState.VERIFIED.value:
            return _unverified_license()
        if record.get("terms_version") != TERMS_VERSION_REVIEWED:
            return _unverified_license()

        authorization_path = _repository_evidence_path(
            str(record["authorization_evidence_file"])
        )
        terms_path = _repository_evidence_path(str(record["terms_evidence_file"]))
        authorization_hash = _sha256_file(authorization_path)
        terms_hash = _sha256_file(terms_path)
        if authorization_hash != record.get("authorization_evidence_sha256"):
            return _unverified_license()
        if terms_hash != record.get("terms_evidence_sha256"):
            return _unverified_license()

        scopes = frozenset(str(scope) for scope in record.get("authorized_scopes", []))
        if not REQUIRED_COMMERCIAL_SCOPES.issubset(scopes):
            return _unverified_license()

        evidence = EvidenceLedgerEntry(
            vendor=VENDOR,
            source_url=str(record["source_url"]),
            document_title=str(record["document_title"]),
            retrieved_at=str(record["reviewed_at"]),
            effective_date=str(record["effective_date"]),
            terms_version=TERMS_VERSION_REVIEWED,
            sha256_content_hash=authorization_hash,
            claim=str(record["claim"]),
            evidence_excerpt_reference=str(record["evidence_excerpt_reference"]),
            epistemic_classification=EpistemicClassification(
                str(record["epistemic_classification"])
            ),
            authorization_scope=tuple(sorted(scopes)),
            superseded_by=None,
            reviewer=str(record["reviewer"]),
            approval_state=ApprovalState(str(record["approval_state"])),
        )
        if evidence.validation_errors():
            return _unverified_license()

        state = VendorLicenseState(
            authorization_state=AuthorizationState.VERIFIED,
            authorized_scopes=scopes,
            stored_terms_hash=str(record["terms_evidence_sha256"]),
            verified_terms_hash=terms_hash,
            terms_version=TERMS_VERSION_REVIEWED,
            reviewed_at=str(record["reviewed_at"]),
            evidence=(evidence,),
        )
        return state if state.commercial_runtime_authorized() else _unverified_license()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return _unverified_license()


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    monetized: bool
    automated_use: bool
    target_site_rights_valid: bool
    sensitive: bool
    requires_zdr: bool
    zdr_entitlement_verified: bool
    zdr_endpoint_verified: bool
    requested_scopes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class GateDenial:
    code: DenialCode
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True)
class RuntimeGateDecision:
    allowed: bool
    request_id: str
    denials: tuple[GateDenial, ...]
    policy_id: str = POLICY_ID

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "request_id": self.request_id,
            "policy_id": self.policy_id,
            "denials": [denial.as_dict() for denial in self.denials],
        }


def evaluate_request(
    request: RequestContext, license_state: VendorLicenseState
) -> RuntimeGateDecision:
    denials: list[GateDenial] = []
    if (
        request.monetized
        and license_state.authorization_state is not AuthorizationState.VERIFIED
    ):
        denials.append(
            GateDenial(
                DenialCode.COMMERCIAL_AUTHORIZATION_NOT_VERIFIED,
                f"Monetized runtime requires VERIFIED authorization; current state is {license_state.authorization_state.value}",
            )
        )
    if not is_sha256(license_state.stored_terms_hash) or not is_sha256(
        license_state.verified_terms_hash
    ):
        denials.append(
            GateDenial(
                DenialCode.TERMS_HASH_MISSING,
                "Stored and current verified Terms hashes are required",
            )
        )
    elif license_state.stored_terms_hash != license_state.verified_terms_hash:
        denials.append(
            GateDenial(
                DenialCode.TERMS_HASH_MISMATCH,
                "Stored Terms hash differs from the current verified Terms hash",
            )
        )

    if request.automated_use and (
        "automated_api_use" not in license_state.authorized_scopes
        or not license_state.has_approved_evidence("automated_api_use")
    ):
        denials.append(
            GateDenial(
                DenialCode.AUTOMATED_USE_NOT_AUTHORIZED,
                "Automated/API/MCP use lacks approved scoped evidence",
            )
        )

    required_scopes = set(request.requested_scopes)
    if request.monetized:
        required_scopes.update(REQUIRED_COMMERCIAL_SCOPES)
    missing_scopes = sorted(
        scope
        for scope in required_scopes
        if scope not in license_state.authorized_scopes
        or not license_state.has_approved_evidence(scope)
    )
    if missing_scopes:
        denials.append(
            GateDenial(
                DenialCode.SCOPE_NOT_AUTHORIZED,
                f"Missing approved authorization scopes: {', '.join(missing_scopes)}",
            )
        )
    if not request.target_site_rights_valid:
        denials.append(
            GateDenial(
                DenialCode.TARGET_SITE_RIGHTS_FAILED,
                "Independent target-site rights validation failed",
            )
        )
    if (
        request.sensitive
        and request.requires_zdr
        and (not request.zdr_entitlement_verified or not request.zdr_endpoint_verified)
    ):
        denials.append(
            GateDenial(
                DenialCode.ZDR_NOT_VERIFIED,
                "Sensitive processing requires verified ZDR entitlement and endpoint support",
            )
        )
    return RuntimeGateDecision(not denials, request.request_id, tuple(denials))


class ContextDevPolicyDenied(RuntimeError):
    def __init__(self, decision: RuntimeGateDecision):
        self.decision = decision
        codes = ", ".join(denial.code.value for denial in decision.denials)
        super().__init__(f"Context.dev request denied: {codes}")


class GovernedContextDevAdapter:
    """Server-side transport boundary guarded by the commercial resolver."""

    def __init__(
        self,
        state_provider: Callable[[], VendorLicenseState],
        transport: Callable[[Mapping[str, Any]], Any],
    ) -> None:
        self._state_provider = state_provider
        self._transport = transport

    def execute(self, context: RequestContext, payload: Mapping[str, Any]) -> Any:
        decision = evaluate_request(context, self._state_provider())
        if not decision.allowed:
            raise ContextDevPolicyDenied(decision)
        return self._transport(payload)


@dataclass(frozen=True)
class TermsChangeResult:
    changed: bool
    material: bool
    stream: ChangeStream
    matched_topics: tuple[str, ...]
    next_authorization_state: AuthorizationState | None


def classify_terms_change(
    previous_sha256: str,
    current_sha256: str,
    changed_topics: Sequence[str],
    stream: ChangeStream,
) -> TermsChangeResult:
    changed = previous_sha256 != current_sha256
    normalized = tuple(topic.strip().lower() for topic in changed_topics)
    matched = tuple(
        topic
        for topic in sorted(MATERIAL_LEGAL_TOPICS)
        if any(topic in candidate or candidate in topic for candidate in normalized)
    )
    material = changed and stream is ChangeStream.LEGAL_LICENSE and bool(matched)
    return TermsChangeResult(
        changed=changed,
        material=material,
        stream=stream,
        matched_topics=matched,
        next_authorization_state=AuthorizationState.REVALIDATION_REQUIRED
        if material
        else None,
    )


@dataclass(frozen=True)
class WatchTarget:
    name: str
    url: str
    stream: ChangeStream
    allowed_hostname: str


@dataclass(frozen=True)
class WatchSnapshot:
    name: str
    source_url: str
    retrieved_at: str
    status: int
    etag: str | None
    last_modified: str | None
    sha256_content_hash: str


class TermsWatcherError(RuntimeError):
    pass


def _validate_public_https_target(target: WatchTarget) -> None:
    parsed = urlsplit(target.url)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise TermsWatcherError(
            "watch target must use credential-free HTTPS on port 443"
        )
    hostname = (parsed.hostname or "").lower().rstrip(".")
    allowed = target.allowed_hostname.lower().rstrip(".")
    if hostname != allowed:
        raise TermsWatcherError("watch target hostname is not allowlisted")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise TermsWatcherError("watch target DNS resolution failed") from exc
    if not addresses or any(
        not ipaddress.ip_address(address).is_global for address in addresses
    ):
        raise TermsWatcherError(
            "watch target did not resolve exclusively to public addresses"
        )


def retrieve_watch_target(
    target: WatchTarget,
    *,
    timeout_seconds: float = 10.0,
    max_bytes: int = 2_000_000,
    client: httpx.Client | None = None,
) -> WatchSnapshot:
    """Retrieve a legal/technical source independently; redirects fail closed."""
    _validate_public_https_target(target)
    owns_client = client is None
    active_client = client or httpx.Client(
        timeout=timeout_seconds, follow_redirects=False
    )
    try:
        with active_client.stream(
            "GET",
            target.url,
            headers={
                "Accept": "text/html,application/xhtml+xml,text/plain",
                "User-Agent": "SARA-OMEGA-Terms-Watcher/1.0",
            },
        ) as response:
            if response.status_code != 200:
                raise TermsWatcherError(
                    f"{target.name} returned HTTP {response.status_code}"
                )
            declared = int(response.headers.get("content-length", "0") or "0")
            if declared > max_bytes:
                raise TermsWatcherError(
                    f"{target.name} exceeds the response-size limit"
                )
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise TermsWatcherError(
                        f"{target.name} exceeded the response-size limit"
                    )
                chunks.append(chunk)
            normalized = b" ".join(b"".join(chunks).replace(b"\r\n", b"\n").split())
            return WatchSnapshot(
                name=target.name,
                source_url=target.url,
                retrieved_at=utc_iso(),
                status=response.status_code,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                sha256_content_hash=hashlib.sha256(normalized).hexdigest(),
            )
    except httpx.HTTPError as exc:
        raise TermsWatcherError(
            f"{target.name} retrieval failed: {type(exc).__name__}"
        ) from exc
    finally:
        if owns_client:
            active_client.close()


PENDING_CONTEXT_DEV_LICENSE = VendorLicenseState.pending_msa()
