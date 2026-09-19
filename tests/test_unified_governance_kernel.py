from dataclasses import replace
from datetime import date

from sara_unified.governance.unified_kernel import (
    ActionRequest,
    ActorIdentity,
    Coverage,
    CoverageRequirement,
    Decision,
    GateStatus,
    GovernancePolicy,
    IndependentEvidenceVerifier,
    InsurancePolicy,
    InsuranceRequirementSet,
    SARAUnifiedGovernanceKernel,
    StateTransition,
)


SIGNING_KEY = b"test-signing-key-long-enough"


def _actor(capabilities=("records:delete",), authenticated=True):
    return ActorIdentity(
        actor_id="agent-1",
        actor_type="agent",
        tenant_id="tenant-1",
        authenticated=authenticated,
        roles=("operator",),
        capabilities=capabilities,
    )


def _transition(reversible=True, production=False):
    return StateTransition(
        resource="customer-db",
        from_state="ACTIVE",
        to_state="ARCHIVED",
        reversible=reversible,
        production=production,
    )


def _request(**overrides):
    values = {
        "request_id": "req-1",
        "actor": _actor(),
        "action": "archive_records",
        "resource": "customer-db",
        "tool": "postgres-admin",
        "jurisdiction": "Georgia",
        "requested_capability": "records:delete",
        "transition": _transition(),
        "input_provenance_ok": True,
    }
    values.update(overrides)
    return ActionRequest(**values)


def _policy(**overrides):
    values = {
        "policy_id": "sara-policy",
        "version": "2026.09",
        "allowed_actions": ("archive_records",),
        "allowed_tools": ("postgres-admin",),
        "allowed_state_transitions": (("ACTIVE", "ARCHIVED"),),
        "max_risk_score": 0.60,
        "quarantine_risk_score": 0.90,
    }
    values.update(overrides)
    return GovernancePolicy(**values)


def test_low_risk_authorized_request_is_allowed_and_verifiable():
    evidence = SARAUnifiedGovernanceKernel(SIGNING_KEY).evaluate(_request(), _policy())

    assert evidence.decision == Decision.ALLOW
    assert evidence.risk_score == 0.0
    assert {gate.name: gate.status for gate in evidence.gate_results}[
        "human_approval"
    ] == GateStatus.NOT_REQUIRED
    assert IndependentEvidenceVerifier.verify(evidence, SIGNING_KEY) == (
        True,
        "Evidence hash and signature are valid.",
    )


def test_unauthorized_request_is_denied_instead_of_escalated():
    request = _request(actor=_actor(capabilities=()))

    evidence = SARAUnifiedGovernanceKernel(SIGNING_KEY).evaluate(request, _policy())

    assert evidence.decision == Decision.DENY
    authority = next(gate for gate in evidence.gate_results if gate.name == "authority")
    assert authority.status == GateStatus.FAIL


def test_review_level_risk_escalates_and_requires_human_approval():
    request = _request(
        transition=_transition(reversible=False, production=True),
        affected_records=50_000,
        contains_sensitive_data=True,
        high_impact_domain=True,
        autonomous=True,
    )

    evidence = SARAUnifiedGovernanceKernel(SIGNING_KEY).evaluate(request, _policy())

    assert evidence.decision == Decision.ESCALATE
    gates = {gate.name: gate for gate in evidence.gate_results}
    assert gates["counterfactual_risk"].status == GateStatus.REVIEW
    assert gates["human_approval"].status == GateStatus.REVIEW


def test_quarantine_level_risk_quarantines_even_with_human_approval():
    request = _request(
        transition=_transition(reversible=False, production=True),
        affected_records=10_000_000,
        financial_value_usd=500_000_000,
        contains_sensitive_data=True,
        high_impact_domain=True,
        external_network_access=True,
        autonomous=True,
        anomaly_score=1.0,
        human_approval_id="approval-1",
    )

    evidence = SARAUnifiedGovernanceKernel(SIGNING_KEY).evaluate(request, _policy())

    assert evidence.decision == Decision.QUARANTINE
    assert evidence.risk_score >= 0.90


def test_insurance_exclusion_fails_required_coverage_gate():
    request = _request(autonomous=True)
    policy = _policy(require_insurance_for_autonomous=True)
    insurance_policy = InsurancePolicy(
        policy_id="POL-1",
        carrier="Example Carrier",
        named_insured="ACME AI Systems",
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        jurisdictions=("Georgia",),
        verified_by="broker-api",
        verification_reference="ref-1",
        coverages=(
            Coverage(
                name="Technology E&O",
                limit_usd=5_000_000,
                exclusions=("Autonomous agent activity",),
            ),
        ),
    )
    requirements = InsuranceRequirementSet(
        requirement_id="AI-RISK-1",
        expected_named_insured="ACME AI Systems",
        allowed_jurisdictions=("Georgia",),
        requirements=(
            CoverageRequirement(
                coverage_name="Technology E&O",
                minimum_limit_usd=5_000_000,
                forbidden_exclusion_keywords=("autonomous agent",),
            ),
        ),
    )

    evidence = SARAUnifiedGovernanceKernel(SIGNING_KEY).evaluate(
        request,
        policy,
        insurance_policy=insurance_policy,
        insurance_requirements=requirements,
    )

    assert evidence.decision == Decision.DENY
    insurance_gate = next(
        gate for gate in evidence.gate_results if gate.name == "insurance_coverage"
    )
    assert insurance_gate.status == GateStatus.FAIL
    assert "disqualifying exclusion" in insurance_gate.reason


def test_tampered_evidence_fails_independent_verification():
    evidence = SARAUnifiedGovernanceKernel(SIGNING_KEY).evaluate(_request(), _policy())
    tampered = replace(evidence, risk_score=evidence.risk_score + 0.1)

    assert IndependentEvidenceVerifier.verify(tampered, SIGNING_KEY) == (
        False,
        "Evidence hash mismatch.",
    )
