# SARA-OMEGA Unified Governance Kernel

`sara_unified.governance.unified_kernel` is a deterministic runtime enforcement point for proposed AI or agent actions. It is designed for use at the boundary before execution, where an LLM may propose an action but does not decide whether execution is allowed.

## Evaluation Gates

The kernel evaluates each `ActionRequest` against:

- identity authentication
- actor capability authority
- configured action, tool, tag, and state-transition policy
- input provenance
- counterfactual risk score
- human approval requirements
- configured insurance coverage requirements

Hard gate failures return `Decision.DENY`. Risk at or above the quarantine threshold returns `Decision.QUARANTINE` unless a hard gate already denied the request. Review gates return `Decision.ESCALATE`. A request is allowed only when every required gate passes.

## Insurance Boundary

The insurance validator does not determine what coverage is legally required. A caller supplies an `InsuranceRequirementSet` from contract terms, organizational policy, broker or insurer data, counsel or compliance guidance, or applicable law. The validator then checks the supplied `InsurancePolicy` for active dates, named insured, jurisdiction, carrier verification, coverage limits, disqualifying exclusions, and required endorsements.

## Evidence Verification

Every evaluation returns `ExecutionEvidence` with gate results, risk factors, a digest of the request, an optional previous evidence hash, an evidence hash, and an HMAC signature. `IndependentEvidenceVerifier.verify()` recomputes the hash and signature and rejects tampered evidence.

## Minimal Example

```python
from sara_unified.governance import (
    ActionRequest,
    ActorIdentity,
    GovernancePolicy,
    IndependentEvidenceVerifier,
    SARAUnifiedGovernanceKernel,
    StateTransition,
)

signing_key = b"replace-with-secret-from-kms"
kernel = SARAUnifiedGovernanceKernel(signing_key)

request = ActionRequest(
    request_id="req-1",
    actor=ActorIdentity(
        actor_id="agent-1",
        actor_type="agent",
        tenant_id="tenant-1",
        authenticated=True,
        capabilities=("records:archive",),
    ),
    action="archive_records",
    resource="customer-db",
    tool="postgres-admin",
    jurisdiction="Georgia",
    requested_capability="records:archive",
    transition=StateTransition(
        resource="customer-db",
        from_state="ACTIVE",
        to_state="ARCHIVED",
        reversible=True,
        production=False,
    ),
    input_provenance_ok=True,
)

policy = GovernancePolicy(
    policy_id="sara-policy",
    version="2026.09",
    allowed_actions=("archive_records",),
    allowed_tools=("postgres-admin",),
    allowed_state_transitions=(("ACTIVE", "ARCHIVED"),),
)

evidence = kernel.evaluate(request, policy)
ok, message = IndependentEvidenceVerifier.verify(evidence, signing_key)
```

Keep the signing key outside source control and replace HMAC with the deployment's chosen KMS, HSM, or asymmetric signing mechanism when the verifier runs across a separate trust boundary.

## Production Enforcement Boundary

The `sara_unified` runtime places consequential side effects behind
`ProductionEnforcementBoundary`. Authorization by the API layer is necessary
but is not sufficient to execute an operation.

For each protected operation the boundary:

1. verifies that the tamper-evident audit chain is intact;
2. constructs a deterministic `ActionRequest` from the authenticated runtime context;
3. evaluates identity, capability authority, policy, state transition, provenance,
   counterfactual risk, human approval, and configured insurance gates;
4. writes the complete signed `ExecutionEvidence` to the audit ledger;
5. permits the side effect only when the decision is exactly `ALLOW`.

`DENY`, `ESCALATE`, `QUARANTINE`, a missing production signing key, an
invalid audit chain, or failure to persist the authorization evidence all block
execution.

The protected unified-runtime operations are:

- digital-twin canonical mutation;
- incident creation;
- recovery execution;
- voice synthesis/external voice side effects.

Production configuration uses:

- `SARA_GOVERNANCE_ENFORCEMENT_REQUIRED=true` by default when loading from the environment;
- `SARA_GOVERNANCE_SIGNING_KEY` for the current HMAC evidence signer;
- `SARA_GOVERNANCE_TENANT_ID` to bind runtime evidence to a tenant context.

The current HMAC key remains a same-trust-domain mechanism. A separate
asymmetric KMS/HSM-backed signer and public-key ROAD verifier remain the next
trust-boundary hardening step.

