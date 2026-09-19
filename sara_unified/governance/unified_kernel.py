"""Deterministic SARA-OMEGA governance kernel.

The kernel evaluates proposed AI or agent actions before execution. It does
not ask a model whether execution is allowed; policy predicates and evidence
verification are deterministic.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from hashlib import sha256, sha512
import hmac
import json
import math
from typing import Any, Iterable, Mapping, Optional, Sequence

from .asymmetric_signing import EvidenceSignature, EvidenceSigner


class Decision(str, Enum):
    ALLOW = "ALLOW"
    RESTRICT = "RESTRICT"
    ESCALATE = "ESCALATE"
    QUARANTINE = "QUARANTINE"
    DENY = "DENY"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True)
class GateResult:
    name: str
    status: GateStatus
    reason: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in {GateStatus.PASS, GateStatus.NOT_REQUIRED}


@dataclass(frozen=True)
class ActorIdentity:
    actor_id: str
    actor_type: str
    tenant_id: str
    authenticated: bool
    roles: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class StateTransition:
    resource: str
    from_state: str
    to_state: str
    reversible: bool
    production: bool


@dataclass(frozen=True)
class ActionRequest:
    request_id: str
    actor: ActorIdentity
    action: str
    resource: str
    tool: str
    jurisdiction: str
    requested_capability: str
    transition: StateTransition
    input_provenance_ok: bool
    policy_tags: tuple[str, ...] = ()
    affected_records: int = 0
    financial_value_usd: float = 0.0
    contains_sensitive_data: bool = False
    high_impact_domain: bool = False
    anomaly_score: float = 0.0
    external_network_access: bool = False
    autonomous: bool = False
    human_approval_id: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GovernancePolicy:
    policy_id: str
    version: str
    allowed_actions: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_state_transitions: tuple[tuple[str, str], ...]
    prohibited_tags: tuple[str, ...] = ()
    require_human_for_irreversible: bool = True
    require_human_for_high_impact: bool = True
    require_human_for_financial_over_usd: float = 10_000.0
    require_insurance_for_autonomous: bool = False
    require_insurance_for_high_impact: bool = False
    max_records_without_human: int = 1_000
    max_risk_score: float = 0.60
    quarantine_risk_score: float = 0.90


@dataclass(frozen=True)
class Coverage:
    name: str
    limit_usd: float
    deductible_usd: float = 0.0
    endorsements: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()


@dataclass(frozen=True)
class InsurancePolicy:
    policy_id: str
    carrier: str
    named_insured: str
    effective_date: date
    expiration_date: date
    coverages: tuple[Coverage, ...]
    jurisdictions: tuple[str, ...] = ()
    verified_by: Optional[str] = None
    verification_reference: Optional[str] = None


@dataclass(frozen=True)
class CoverageRequirement:
    coverage_name: str
    minimum_limit_usd: float
    forbidden_exclusion_keywords: tuple[str, ...] = ()
    required_endorsement_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class InsuranceRequirementSet:
    requirement_id: str
    expected_named_insured: str
    requirements: tuple[CoverageRequirement, ...]
    allowed_jurisdictions: tuple[str, ...] = ()
    carrier_verification_required: bool = True


@dataclass(frozen=True)
class InsuranceValidation:
    status: GateStatus
    reasons: tuple[str, ...]
    matched_coverages: Mapping[str, Mapping[str, Any]]
    policy_active: bool
    named_insured_match: bool
    jurisdiction_match: bool
    carrier_verified: bool


@dataclass(frozen=True)
class ExecutionEvidence:
    evidence_version: str
    issued_at: str
    request_id: str
    decision: Decision
    policy_id: str
    policy_version: str
    gate_results: tuple[GateResult, ...]
    risk_score: float
    risk_factors: Mapping[str, float]
    request_digest: str
    previous_evidence_hash: Optional[str]
    evidence_hash: str
    signing_digest_b64: str = ""
    signatures: tuple[EvidenceSignature, ...] = ()
    signature: str = ""


def _canonical_json(value: Any) -> str:
    def default(obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        raise TypeError(f"Unsupported value: {type(obj)!r}")

    return json.dumps(value, default=default, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("_", " ").replace("-", " ").split())


def _contains_keyword(items: Iterable[str], keyword: str) -> bool:
    needle = _normalize(keyword)
    return any(needle in _normalize(item) for item in items)


class InsuranceCoverageValidator:
    """Validate supplied insurance evidence against configured requirements."""

    @staticmethod
    def validate(
        policy: Optional[InsurancePolicy],
        requirements: Optional[InsuranceRequirementSet],
        jurisdiction: str,
        as_of: Optional[date] = None,
    ) -> InsuranceValidation:
        if requirements is None:
            return InsuranceValidation(
                status=GateStatus.NOT_REQUIRED,
                reasons=("No insurance requirement applies to this action.",),
                matched_coverages={},
                policy_active=True,
                named_insured_match=True,
                jurisdiction_match=True,
                carrier_verified=True,
            )

        if policy is None:
            return InsuranceValidation(
                status=GateStatus.FAIL,
                reasons=("Required insurance evidence was not supplied.",),
                matched_coverages={},
                policy_active=False,
                named_insured_match=False,
                jurisdiction_match=False,
                carrier_verified=False,
            )

        today = as_of or datetime.now(timezone.utc).date()
        reasons: list[str] = []
        matched: dict[str, Mapping[str, Any]] = {}

        policy_active = policy.effective_date <= today <= policy.expiration_date
        if not policy_active:
            reasons.append("Insurance policy is not active for the evaluation date.")

        named_insured_match = (
            _normalize(policy.named_insured)
            == _normalize(requirements.expected_named_insured)
        )
        if not named_insured_match:
            reasons.append("Named insured does not match the required organization.")

        if requirements.allowed_jurisdictions:
            jurisdiction_allowed = any(
                _normalize(jurisdiction) == _normalize(item)
                for item in requirements.allowed_jurisdictions
            )
        else:
            jurisdiction_allowed = True

        policy_jurisdiction_ok = not policy.jurisdictions or any(
            _normalize(jurisdiction) == _normalize(item)
            for item in policy.jurisdictions
        )
        jurisdiction_match = jurisdiction_allowed and policy_jurisdiction_ok
        if not jurisdiction_match:
            reasons.append(
                "Policy does not establish coverage for the requested jurisdiction."
            )

        carrier_verified = bool(policy.verified_by and policy.verification_reference)
        if requirements.carrier_verification_required and not carrier_verified:
            reasons.append(
                "Carrier/broker verification evidence is required but missing."
            )

        coverage_failed = False
        for requirement in requirements.requirements:
            candidates = [
                coverage
                for coverage in policy.coverages
                if _normalize(coverage.name) == _normalize(requirement.coverage_name)
            ]
            if not candidates:
                coverage_failed = True
                reasons.append(
                    f"Required coverage missing: {requirement.coverage_name}."
                )
                continue

            coverage = max(candidates, key=lambda item: item.limit_usd)
            details: dict[str, Any] = {
                "limit_usd": coverage.limit_usd,
                "required_limit_usd": requirement.minimum_limit_usd,
                "deductible_usd": coverage.deductible_usd,
                "endorsements": list(coverage.endorsements),
                "exclusions": list(coverage.exclusions),
            }

            if coverage.limit_usd < requirement.minimum_limit_usd:
                coverage_failed = True
                reasons.append(
                    f"{requirement.coverage_name} limit is below requirement "
                    f"(${coverage.limit_usd:,.0f} < "
                    f"${requirement.minimum_limit_usd:,.0f})."
                )

            bad_exclusions = [
                keyword
                for keyword in requirement.forbidden_exclusion_keywords
                if _contains_keyword(coverage.exclusions, keyword)
            ]
            if bad_exclusions:
                coverage_failed = True
                details["matched_forbidden_exclusions"] = bad_exclusions
                reasons.append(
                    f"{requirement.coverage_name} contains disqualifying "
                    f"exclusion(s): {', '.join(bad_exclusions)}"
                )

            missing_endorsements = [
                keyword
                for keyword in requirement.required_endorsement_keywords
                if not _contains_keyword(coverage.endorsements, keyword)
            ]
            if missing_endorsements:
                coverage_failed = True
                details["missing_required_endorsements"] = missing_endorsements
                reasons.append(
                    f"{requirement.coverage_name} lacks required endorsement(s): "
                    f"{', '.join(missing_endorsements)}"
                )

            matched[requirement.coverage_name] = details

        hard_fail = (
            not policy_active
            or not named_insured_match
            or not jurisdiction_match
            or (requirements.carrier_verification_required and not carrier_verified)
            or coverage_failed
        )
        if not hard_fail:
            reasons.append(
                "Insurance evidence satisfies the configured requirement set."
            )

        return InsuranceValidation(
            status=GateStatus.FAIL if hard_fail else GateStatus.PASS,
            reasons=tuple(reasons),
            matched_coverages=matched,
            policy_active=policy_active,
            named_insured_match=named_insured_match,
            jurisdiction_match=jurisdiction_match,
            carrier_verified=carrier_verified,
        )


class CounterfactualRiskEngine:
    """Deterministic governance risk estimator for proposed actions."""

    @staticmethod
    def evaluate(request: ActionRequest) -> tuple[float, dict[str, float]]:
        factors: dict[str, float] = {}

        if request.transition.production:
            factors["production"] = 0.10
        if not request.transition.reversible:
            factors["irreversible"] = 0.18
        if request.contains_sensitive_data:
            factors["sensitive_data"] = 0.12
        if request.high_impact_domain:
            factors["high_impact_domain"] = 0.18
        if request.external_network_access:
            factors["external_network_access"] = 0.08
        if request.autonomous:
            factors["autonomous_agent"] = 0.10

        if request.affected_records > 0:
            factors["records_affected"] = min(
                0.16, max(0.0, math.log10(request.affected_records + 1) / 30)
            )

        if request.financial_value_usd > 0:
            factors["financial_value"] = min(
                0.18,
                max(0.0, math.log10(request.financial_value_usd + 1) / 35),
            )

        if request.anomaly_score > 0:
            factors["behavioral_anomaly"] = min(0.20, request.anomaly_score * 0.20)

        return round(min(1.0, sum(factors.values())), 4), factors


class SARAUnifiedGovernanceKernel:
    """Runtime enforcement point for governed SARA-OMEGA actions."""

    def __init__(
        self,
        signing_key: bytes | None = None,
        *,
        evidence_signer: EvidenceSigner | None = None,
    ):
        if signing_key is not None and evidence_signer is not None:
            raise ValueError("configure either legacy signing_key or evidence_signer, not both")
        if evidence_signer is None:
            if not signing_key or len(signing_key) < 16:
                raise ValueError("signing authority is required")
            self._signing_key = signing_key
        else:
            self._signing_key = None
        self._evidence_signer = evidence_signer

    def evaluate(
        self,
        request: ActionRequest,
        policy: GovernancePolicy,
        insurance_policy: Optional[InsurancePolicy] = None,
        insurance_requirements: Optional[InsuranceRequirementSet] = None,
        previous_evidence_hash: Optional[str] = None,
    ) -> ExecutionEvidence:
        gates: list[GateResult] = []

        if request.actor.authenticated and request.actor.actor_id and request.actor.tenant_id:
            gates.append(
                GateResult(
                    "identity",
                    GateStatus.PASS,
                    "Actor identity is authenticated.",
                    {
                        "actor_id": request.actor.actor_id,
                        "actor_type": request.actor.actor_type,
                    },
                )
            )
        else:
            gates.append(
                GateResult(
                    "identity",
                    GateStatus.FAIL,
                    "Actor identity is not authenticated.",
                )
            )

        if request.requested_capability in request.actor.capabilities:
            gates.append(
                GateResult(
                    "authority",
                    GateStatus.PASS,
                    "Actor possesses the requested capability.",
                    {"capability": request.requested_capability},
                )
            )
        else:
            gates.append(
                GateResult(
                    "authority",
                    GateStatus.FAIL,
                    "Actor lacks the requested capability.",
                    {"capability": request.requested_capability},
                )
            )

        prohibited = set(policy.prohibited_tags).intersection(request.policy_tags)
        policy_reasons: list[str] = []
        if request.action not in policy.allowed_actions:
            policy_reasons.append("action not allowed")
        if request.tool not in policy.allowed_tools:
            policy_reasons.append("tool not allowed")
        if prohibited:
            policy_reasons.append("prohibited tags: " + ", ".join(sorted(prohibited)))

        gates.append(
            GateResult(
                "policy",
                GateStatus.FAIL if policy_reasons else GateStatus.PASS,
                "Policy violation: " + "; ".join(policy_reasons)
                if policy_reasons
                else "Action satisfies configured policy.",
                {"policy_tags": list(request.policy_tags)},
            )
        )

        transition_pair = (request.transition.from_state, request.transition.to_state)
        gates.append(
            GateResult(
                "state_transition",
                GateStatus.PASS
                if transition_pair in policy.allowed_state_transitions
                else GateStatus.FAIL,
                "Requested state transition is allowed."
                if transition_pair in policy.allowed_state_transitions
                else "Requested state transition is not allowed.",
                {
                    "transition": list(transition_pair),
                    "resource": request.transition.resource,
                },
            )
        )

        gates.append(
            GateResult(
                "provenance",
                GateStatus.PASS if request.input_provenance_ok else GateStatus.FAIL,
                "Input provenance is established."
                if request.input_provenance_ok
                else "Input provenance is missing or invalid.",
            )
        )

        risk_score, risk_factors = CounterfactualRiskEngine.evaluate(request)
        if risk_score >= policy.quarantine_risk_score:
            risk_status = GateStatus.FAIL
            risk_reason = (
                f"Counterfactual risk score {risk_score:.2f} meets/exceeds "
                f"quarantine threshold {policy.quarantine_risk_score:.2f}."
            )
        elif risk_score > policy.max_risk_score:
            risk_status = GateStatus.REVIEW
            risk_reason = (
                f"Counterfactual risk score {risk_score:.2f} exceeds "
                f"normal execution threshold {policy.max_risk_score:.2f}."
            )
        else:
            risk_status = GateStatus.PASS
            risk_reason = (
                f"Counterfactual risk score {risk_score:.2f} is within threshold."
            )
        gates.append(
            GateResult(
                "counterfactual_risk",
                risk_status,
                risk_reason,
                {"factors": risk_factors},
            )
        )

        human_required = (
            (policy.require_human_for_irreversible and not request.transition.reversible)
            or (policy.require_human_for_high_impact and request.high_impact_domain)
            or request.financial_value_usd >= policy.require_human_for_financial_over_usd
            or request.affected_records > policy.max_records_without_human
            or risk_status == GateStatus.REVIEW
        )
        if human_required:
            gates.append(
                GateResult(
                    "human_approval",
                    GateStatus.PASS
                    if request.human_approval_id
                    else GateStatus.REVIEW,
                    "Required human approval is present."
                    if request.human_approval_id
                    else "Human approval is required before execution.",
                    {"approval_id": request.human_approval_id}
                    if request.human_approval_id
                    else {},
                )
            )
        else:
            gates.append(
                GateResult(
                    "human_approval",
                    GateStatus.NOT_REQUIRED,
                    "Human approval is not required for this action.",
                )
            )

        insurance_required = (
            insurance_requirements is not None
            or (policy.require_insurance_for_autonomous and request.autonomous)
            or (policy.require_insurance_for_high_impact and request.high_impact_domain)
        )
        if insurance_required and insurance_requirements is None:
            gates.append(
                GateResult(
                    "insurance_coverage",
                    GateStatus.REVIEW,
                    "Insurance is required by governance policy, but no "
                    "requirement set was supplied. Legal/contractual "
                    "requirements must be configured.",
                )
            )
        elif insurance_required:
            insurance = InsuranceCoverageValidator.validate(
                insurance_policy,
                insurance_requirements,
                request.jurisdiction,
            )
            gates.append(
                GateResult(
                    "insurance_coverage",
                    insurance.status,
                    " ".join(insurance.reasons),
                    {
                        "policy_active": insurance.policy_active,
                        "named_insured_match": insurance.named_insured_match,
                        "jurisdiction_match": insurance.jurisdiction_match,
                        "carrier_verified": insurance.carrier_verified,
                        "matched_coverages": insurance.matched_coverages,
                    },
                )
            )
        else:
            gates.append(
                GateResult(
                    "insurance_coverage",
                    GateStatus.NOT_REQUIRED,
                    "No configured insurance requirement applies to this action.",
                )
            )

        decision = self._aggregate_decision(gates, risk_score, policy)
        issued_at = datetime.now(timezone.utc).isoformat()
        request_digest = _digest(request)
        unsigned = self._unsigned_evidence_payload(
            evidence_version="1.0",
            issued_at=issued_at,
            request_id=request.request_id,
            decision=decision,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            gate_results=tuple(gates),
            risk_score=risk_score,
            risk_factors=risk_factors,
            request_digest=request_digest,
            previous_evidence_hash=previous_evidence_hash,
        )

        evidence_hash = _digest(unsigned)
        signing_digest = sha512(_canonical_json(unsigned).encode("utf-8")).digest()
        signing_digest_b64 = base64.b64encode(signing_digest).decode("ascii")
        signatures: tuple[EvidenceSignature, ...] = ()
        signature = ""

        if self._evidence_signer is not None:
            try:
                signatures = tuple(self._evidence_signer.sign_digest(signing_digest))
            except Exception as exc:
                raise RuntimeError("asymmetric_evidence_signing_failed") from exc
            algorithms = [item.algorithm for item in signatures]
            if sorted(algorithms) != ["Ed25519", "ML-DSA"]:
                raise RuntimeError("dual_asymmetric_signatures_required")
        else:
            # Development/backward-compatibility path only. Production
            # enforcement is configured with evidence_signer.
            signature = hmac.new(
                self._signing_key,
                evidence_hash.encode("utf-8"),
                sha256,
            ).hexdigest()

        return ExecutionEvidence(
            evidence_version="1.0",
            issued_at=issued_at,
            request_id=request.request_id,
            decision=decision,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            gate_results=tuple(gates),
            risk_score=risk_score,
            risk_factors=risk_factors,
            request_digest=request_digest,
            previous_evidence_hash=previous_evidence_hash,
            evidence_hash=evidence_hash,
            signing_digest_b64=signing_digest_b64,
            signatures=signatures,
            signature=signature,
        )

    @staticmethod
    def _aggregate_decision(
        gates: Sequence[GateResult],
        risk_score: float,
        policy: GovernancePolicy,
    ) -> Decision:
        by_name = {gate.name: gate for gate in gates}
        hard_gate_names = {
            "identity",
            "authority",
            "policy",
            "state_transition",
            "provenance",
            "insurance_coverage",
        }

        if any(
            by_name[name].status == GateStatus.FAIL
            for name in hard_gate_names
            if name in by_name
        ):
            return Decision.DENY

        if risk_score >= policy.quarantine_risk_score:
            return Decision.QUARANTINE

        if any(gate.status == GateStatus.REVIEW for gate in gates):
            return Decision.ESCALATE

        return Decision.ALLOW

    @staticmethod
    def _unsigned_evidence_payload(
        *,
        evidence_version: str,
        issued_at: str,
        request_id: str,
        decision: Decision,
        policy_id: str,
        policy_version: str,
        gate_results: tuple[GateResult, ...],
        risk_score: float,
        risk_factors: Mapping[str, float],
        request_digest: str,
        previous_evidence_hash: Optional[str],
    ) -> Mapping[str, Any]:
        return {
            "evidence_version": evidence_version,
            "issued_at": issued_at,
            "request_id": request_id,
            "decision": decision.value,
            "policy_id": policy_id,
            "policy_version": policy_version,
            "gate_results": [
                {
                    "name": gate.name,
                    "status": gate.status.value,
                    "reason": gate.reason,
                    "evidence": dict(gate.evidence),
                }
                for gate in gate_results
            ],
            "risk_score": risk_score,
            "risk_factors": dict(risk_factors),
            "request_digest": request_digest,
            "previous_evidence_hash": previous_evidence_hash,
        }


class IndependentEvidenceVerifier:
    """Verify execution evidence from outside the decision path."""

    @staticmethod
    def verify(evidence: ExecutionEvidence, signing_key: bytes) -> tuple[bool, str]:
        unsigned = SARAUnifiedGovernanceKernel._unsigned_evidence_payload(
            evidence_version=evidence.evidence_version,
            issued_at=evidence.issued_at,
            request_id=evidence.request_id,
            decision=evidence.decision,
            policy_id=evidence.policy_id,
            policy_version=evidence.policy_version,
            gate_results=evidence.gate_results,
            risk_score=evidence.risk_score,
            risk_factors=evidence.risk_factors,
            request_digest=evidence.request_digest,
            previous_evidence_hash=evidence.previous_evidence_hash,
        )
        expected_hash = _digest(unsigned)
        if not hmac.compare_digest(expected_hash, evidence.evidence_hash):
            return False, "Evidence hash mismatch."

        if evidence.signatures:
            return False, "Evidence uses asymmetric signatures; verify with ROAD public keys."

        expected_signature = hmac.new(
            signing_key,
            expected_hash.encode("utf-8"),
            sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, evidence.signature):
            return False, "Evidence signature mismatch."

        return True, "Evidence hash and signature are valid."
