"""Fail-closed production enforcement boundary for SARA-OMEGA.

Every consequential operation in the unified runtime must obtain an ALLOW
decision from the deterministic governance kernel before the side effect is
invoked. The complete signed execution evidence is committed to the
tamper-evident audit ledger before execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import secrets
import uuid
from typing import Any, Mapping, Optional

from .asymmetric_signing import EvidenceSigner
from .unified_kernel import (
    ActionRequest,
    ActorIdentity,
    Decision,
    ExecutionEvidence,
    GovernancePolicy,
    InsurancePolicy,
    InsuranceRequirementSet,
    SARAUnifiedGovernanceKernel,
    StateTransition,
)


@dataclass(frozen=True)
class EnforcementProfile:
    action: str
    tool: str
    capability: str
    from_state: str
    to_state: str
    reversible: bool
    production: bool
    external_network_access: bool = False
    high_impact_domain: bool = False


class GovernanceEnforcementError(RuntimeError):
    """Base exception returned when execution cannot cross the boundary."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        decision: Optional[Decision] = None,
        evidence_hash: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.decision = decision
        self.evidence_hash = evidence_hash


class GovernanceUnavailable(GovernanceEnforcementError):
    """The enforcement boundary itself is not trustworthy or available."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class GovernanceBlocked(GovernanceEnforcementError):
    """The kernel evaluated the action but did not authorize execution."""

    def __init__(self, evidence: ExecutionEvidence) -> None:
        status_code = {
            Decision.DENY: 403,
            Decision.RESTRICT: 403,
            Decision.ESCALATE: 403,
            Decision.QUARANTINE: 423,
        }.get(evidence.decision, 403)
        super().__init__(
            f"governance decision {evidence.decision.value} blocks execution",
            status_code=status_code,
            decision=evidence.decision,
            evidence_hash=evidence.evidence_hash,
        )


DEFAULT_PRODUCTION_POLICY = GovernancePolicy(
    policy_id="sara-production-enforcement",
    version="2026.09.19",
    allowed_actions=(
        "twin.observe",
        "incident.create",
        "recovery.execute",
        "voice.synthesize",
    ),
    allowed_tools=(
        "digital-twin",
        "incident-commander",
        "recovery-registry",
        "voice-service",
    ),
    allowed_state_transitions=(
        ("OBSERVED", "CANONICAL"),
        ("NONE", "OPEN"),
        ("DEGRADED", "RECOVERING"),
        ("TEXT_VALIDATED", "AUDIO_SYNTHESIZED"),
    ),
    require_human_for_irreversible=True,
    require_human_for_high_impact=True,
    require_human_for_financial_over_usd=10_000.0,
    max_records_without_human=1_000,
    max_risk_score=0.60,
    quarantine_risk_score=0.90,
)


class ProductionEnforcementBoundary:
    """Single fail-closed gateway between authorization and side effects."""

    def __init__(
        self,
        audit: Any,
        *,
        signing_key: bytes | None,
        evidence_signer: EvidenceSigner | None = None,
        required: bool,
        tenant_id: str,
        policy: GovernancePolicy | None = None,
    ) -> None:
        self.audit = audit
        self.required = required
        self.tenant_id = tenant_id.strip() or "default"
        self.policy = policy or DEFAULT_PRODUCTION_POLICY
        self._kernel: SARAUnifiedGovernanceKernel | None = None
        self._configuration_error: str | None = None

        if evidence_signer is not None:
            try:
                self._kernel = SARAUnifiedGovernanceKernel(
                    evidence_signer=evidence_signer
                )
            except Exception as exc:
                self._configuration_error = type(exc).__name__
        elif signing_key:
            try:
                self._kernel = SARAUnifiedGovernanceKernel(signing_key)
            except Exception as exc:
                self._configuration_error = type(exc).__name__
        elif required:
            self._configuration_error = "missing_asymmetric_signing_authority"
        else:
            # Local/test runtimes still cross the same enforcement code path.
            # The ephemeral key is intentionally non-portable and never claimed
            # as production verification evidence.
            self._kernel = SARAUnifiedGovernanceKernel(secrets.token_bytes(32))

    @property
    def ready(self) -> bool:
        if self._kernel is None:
            return False
        try:
            return bool(self.audit.verify())
        except Exception:
            return False

    def authorize(
        self,
        *,
        profile: EnforcementProfile,
        actor_id: str,
        actor_type: str,
        capabilities: set[str] | tuple[str, ...],
        input_provenance_ok: bool,
        resource: str,
        jurisdiction: str = "unspecified",
        human_approval_id: str | None = None,
        affected_records: int = 0,
        financial_value_usd: float = 0.0,
        contains_sensitive_data: bool = False,
        anomaly_score: float = 0.0,
        autonomous: bool = False,
        policy_tags: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
        insurance_policy: InsurancePolicy | None = None,
        insurance_requirements: InsuranceRequirementSet | None = None,
    ) -> ExecutionEvidence:
        if self._kernel is None:
            self._record_fail_closed(
                action=profile.action,
                reason=self._configuration_error or "kernel_unavailable",
            )
            raise GovernanceUnavailable("production governance kernel is unavailable")

        try:
            audit_valid = bool(self.audit.verify())
        except Exception as exc:
            self._record_fail_closed(
                action=profile.action,
                reason=f"audit_verification_error:{type(exc).__name__}",
            )
            raise GovernanceUnavailable("governance audit verification failed") from exc

        if not audit_valid:
            self._record_fail_closed(
                action=profile.action,
                reason="audit_chain_invalid",
                allow_unverified_audit=True,
            )
            raise GovernanceUnavailable("governance audit chain is invalid")

        capability_set = tuple(sorted(set(capabilities)))
        request = ActionRequest(
            request_id=f"gov-{uuid.uuid4()}",
            actor=ActorIdentity(
                actor_id=actor_id.strip(),
                actor_type=actor_type.strip() or "api",
                tenant_id=self.tenant_id,
                authenticated=bool(actor_id.strip()),
                capabilities=capability_set,
            ),
            action=profile.action,
            resource=resource,
            tool=profile.tool,
            jurisdiction=jurisdiction or "unspecified",
            requested_capability=profile.capability,
            transition=StateTransition(
                resource=resource,
                from_state=profile.from_state,
                to_state=profile.to_state,
                reversible=profile.reversible,
                production=profile.production,
            ),
            input_provenance_ok=input_provenance_ok,
            policy_tags=policy_tags,
            affected_records=max(0, int(affected_records)),
            financial_value_usd=max(0.0, float(financial_value_usd)),
            contains_sensitive_data=contains_sensitive_data,
            high_impact_domain=profile.high_impact_domain,
            anomaly_score=max(0.0, min(1.0, float(anomaly_score))),
            external_network_access=profile.external_network_access,
            autonomous=autonomous,
            human_approval_id=human_approval_id,
            metadata=dict(metadata or {}),
        )

        evidence = self._kernel.evaluate(
            request,
            self.policy,
            insurance_policy=insurance_policy,
            insurance_requirements=insurance_requirements,
        )

        # Persist the complete signed decision before any side effect. If this
        # write fails, the operation is not allowed to execute.
        try:
            self.audit.append(
                "governance-kernel",
                "GOVERNANCE_AUTHORIZATION",
                {
                    "action": profile.action,
                    "resource": resource,
                    "execution_evidence": self.evidence_payload(evidence),
                },
            )
        except Exception as exc:
            raise GovernanceUnavailable(
                "governance authorization evidence could not be persisted"
            ) from exc

        if evidence.decision is not Decision.ALLOW:
            raise GovernanceBlocked(evidence)

        return evidence

    @staticmethod
    def evidence_payload(evidence: ExecutionEvidence) -> dict[str, Any]:
        return {
            "evidence_version": evidence.evidence_version,
            "issued_at": evidence.issued_at,
            "request_id": evidence.request_id,
            "decision": evidence.decision.value,
            "policy_id": evidence.policy_id,
            "policy_version": evidence.policy_version,
            "gate_results": [
                {
                    "name": gate.name,
                    "status": gate.status.value,
                    "reason": gate.reason,
                    "evidence": dict(gate.evidence),
                }
                for gate in evidence.gate_results
            ],
            "risk_score": evidence.risk_score,
            "risk_factors": dict(evidence.risk_factors),
            "request_digest": evidence.request_digest,
            "previous_evidence_hash": evidence.previous_evidence_hash,
            "evidence_hash": evidence.evidence_hash,
            "signing_digest_b64": evidence.signing_digest_b64,
            "signatures": [
                {
                    "algorithm": item.algorithm,
                    "key_id": item.key_id,
                    "signature_b64": item.signature_b64,
                    "backend": item.backend,
                }
                for item in evidence.signatures
            ],
            "signature": evidence.signature,
        }

    def _record_fail_closed(
        self,
        *,
        action: str,
        reason: str,
        allow_unverified_audit: bool = False,
    ) -> None:
        try:
            # This event is diagnostic only. A failed append never changes the
            # fail-closed outcome.
            self.audit.append(
                "governance-kernel",
                "GOVERNANCE_FAIL_CLOSED",
                {
                    "action": action,
                    "reason": reason,
                    "audit_preverified": not allow_unverified_audit,
                },
            )
        except Exception:
            pass
