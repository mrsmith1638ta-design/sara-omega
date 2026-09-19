# SARA Unified Ecosystem Python Build — Design Specification

Date: 2026-09-15
Target release family: SARA-OMEGA 3.2.1+
Implementation language: Python 3.12+
Architecture class: Production-oriented modular monolith with explicit subsystem interfaces

## 1. Objective

Create one unified Python build that combines the SARA Ecosystem Control Plane and the SARA Cognitive Operations Fabric into a single governed runtime. The build must preserve strong module boundaries while presenting one canonical application, one configuration system, one audit/evidence contract, one security/governance authority chain, and one operational entrypoint.

The unified runtime must support:

- ecosystem control plane
- service/module registry
- observability and health aggregation
- governed automated recovery
- evidence fusion and claim provenance
- digital twin of ecosystem state
- model-jury / disagreement resolution
- counterfactual scenario analysis
- knowledge-gap detection
- temporal change intelligence
- adversarial self-testing hooks
- capability provenance passports
- governed skill synthesis
- incident-command coordination
- security enforcement and fail-closed authorization
- immutable/tamper-evident audit records
- ROAD/SIOS-compatible release and authority boundaries

## 2. Architectural Approach

Use a modular monolith first, not a distributed microservice mesh. This gives SARA one deployable Python artifact while keeping subsystems independently testable and replaceable. External services such as ROAD, SIOS, cloud providers, model providers, databases, and telemetry systems are integrated through adapters.

The runtime has five planes:

1. **Governance Plane** — authority, policy, approval, trust, SIOS/ROAD contracts.
2. **Cognitive Plane** — evidence fusion, model jury, counterfactuals, causal/hypothesis analysis, gap detection.
3. **Operations Plane** — digital twin, service registry, observability, incident handling, recovery.
4. **Security Plane** — authentication, authorization, replay resistance, rate limiting, quarantine, circuit breaking, revocation, write freezes.
5. **Evidence Plane** — append-only audit, provenance, capability passports, signed state snapshots, temporal history.

No plane can bypass the Governance or Security planes for state-changing actions.

## 3. Canonical Package Layout

```text
sara_unified/
  __init__.py
  app.py
  cli.py
  config.py
  contracts.py
  errors.py
  governance/
    authority.py
    policy.py
    approvals.py
    road.py
    sios.py
  security/
    identity.py
    authorization.py
    replay.py
    rate_limit.py
    quarantine.py
    circuit_breaker.py
  evidence/
    claims.py
    provenance.py
    fusion.py
    audit.py
    passports.py
    signing.py
  cognition/
    jury.py
    counterfactual.py
    gaps.py
    temporal.py
    causal.py
    experiment.py
  operations/
    registry.py
    digital_twin.py
    observability.py
    recovery.py
    incidents.py
  skills/
    compiler.py
    registry.py
  adapters/
    models.py
    storage.py
    telemetry.py
    road_client.py
    sios_client.py
  api/
    server.py
    schemas.py
    dependencies.py
  persistence/
    db.py
    models.py
    repositories.py
  tests/
```

The public application surface is `sara_unified.app:SARAUnified` and the CLI/server entrypoint is `python -m sara_unified`.

## 4. Core Runtime Flow

Every request follows this sequence:

1. Assign request, session, actor, and correlation identifiers.
2. Authenticate identity.
3. Enforce replay and freshness checks for signed/action requests.
4. Authorize requested capability.
5. Classify operation as read-only, state-changing, sensitive, or destructive.
6. Resolve applicable governance policies and approval requirements.
7. Acquire evidence and current digital-twin state.
8. Execute cognitive analysis or operational plan.
9. For high-impact conclusions, run disagreement/adversarial checks.
10. For state changes, obtain required SIOS/authority decision before execution.
11. Execute through a bounded adapter.
12. Validate result against expected postconditions.
13. Update digital twin only from verified observations.
14. Append audit/evidence records.
15. Emit capability passport / execution receipt where applicable.
16. On failure, classify, contain, and invoke only pre-authorized recovery actions; otherwise escalate and fail closed.

## 5. Evidence Fusion Engine

Material claims are represented as structured claim objects with:

- claim ID
- normalized statement
- source references
- source timestamps
- source type
- evidence digest
- epistemic status
- confidence metadata
- contradiction links
- supersession links
- freshness/expiry

Allowed epistemic states:

`VERIFIED`, `SUPPORTED`, `INFERRED`, `DISPUTED`, `UNVERIFIED`, `UNKNOWN`, `CURRENTLY_INACCESSIBLE`.

The fusion engine must never convert disagreement into false consensus. Contradictions remain explicit until resolved by stronger evidence or authority.

## 6. Digital Twin

The digital twin is the canonical operational graph of:

- modules
- services
- versions
- deployments
- endpoints
- dependencies
- data stores
- external providers
- governance relationships
- security boundaries
- health observations
- configuration digests
- release/evidence references

Twin state is observational, not aspirational. A deployment is marked active only from verified runtime evidence, never merely from repository configuration.

## 7. Model Jury

The jury subsystem accepts multiple independent opinions/results and produces:

- points of agreement
- points of disagreement
- assumptions
- evidence overlap
- evidence independence
- confidence spread
- unresolved questions
- recommended evidence needed to resolve disagreement

It does not select a result based on majority vote alone. Evidence quality and independence are required inputs.

## 8. Counterfactual Engine

Counterfactual scenarios are isolated from production state. Each scenario declares:

- baseline state snapshot
- assumptions
- proposed changes
- constraints
- predicted impacts
- uncertainty
- dependencies
- rollback conditions

Simulation output can inform decisions but cannot directly mutate production.

## 9. Knowledge-Gap Radar

Continuously derives gaps from:

- stale claims
- unresolved contradictions
- undocumented dependencies
- failed/absent tests
- unverified runtime claims
- missing authority records
- configuration drift
- evidence expiration
- uncovered recovery paths
- missing security controls

Each gap has severity, affected capability, evidence, remediation class, and whether human approval is required.

## 10. Governed Recovery

Recovery actions use an allowlisted action registry. Each action defines:

- trigger conditions
- authority level
- blast-radius limit
- preconditions
- execution adapter
- verification step
- rollback action
- audit requirements

Automatic actions are limited to explicitly pre-authorized low-risk operations. Credential rotation, destructive rollback, data mutation, service isolation with business impact, or irreversible actions require configured approval unless an emergency policy explicitly grants authority.

## 11. Incident Commander

The incident subsystem:

- detects or receives incidents
- freezes unsafe operations when policy requires
- builds a timeline
- computes blast radius from the digital twin
- correlates telemetry and evidence
- recommends containment/recovery
- preserves forensic evidence
- tracks approvals/actions
- produces post-incident evidence reports

It does not invent root cause when evidence is insufficient.

## 12. Capability Passports

Every registered capability has a machine-readable passport containing:

- capability ID/name/version
- implementation digest
- dependencies
- required permissions
- governance rules
- security classification
- test evidence
- release evidence
- runtime verification evidence
- known limitations
- evidence expiry
- signing metadata

Passports are signed using application signing keys and verified before trusted registration.

## 13. Governed Skill Synthesis

A workflow may be compiled into a skill only when:

- every step has an explicit interface
- inputs/outputs are typed
- permissions are enumerated
- external effects are identified
- approval gates are defined
- rollback behavior exists when applicable
- tests pass
- security and governance validation pass

Generated skills are not auto-activated. Activation requires registration and policy authorization.

## 14. Security Requirements

Minimum controls:

- default deny authorization
- HMAC or asymmetric request signatures for trusted service calls
- nonce/replay protection
- timestamp freshness
- strong input validation
- bounded payload sizes
- rate limiting
- injection-resistant adapters
- SSRF restrictions
- command execution prohibited by default
- secret redaction
- tenant/session isolation
- quarantine state
- credential/session revocation hooks
- circuit breakers
- write-freeze control
- dependency and capability allowlists
- tamper-evident audit chain

Security state transitions must be audited.

## 15. Persistence

Use SQLAlchemy 2.x with SQLite for local development/tests and PostgreSQL for production. The schema includes:

- audit events
- claims/evidence
- twin entities/edges/observations
- incidents/actions
- approvals
- capability passports
- skill definitions
- security state
- recovery executions

Transactions are explicit. State-changing operations use idempotency keys where appropriate.

## 16. API and CLI

Expose a FastAPI service for operational use and a CLI for local/administrative inspection.

Initial endpoint families:

- `/health`
- `/readyz`
- `/v1/capabilities`
- `/v1/evidence/*`
- `/v1/twin/*`
- `/v1/jury/*`
- `/v1/counterfactual/*`
- `/v1/gaps/*`
- `/v1/incidents/*`
- `/v1/recovery/*`
- `/v1/passports/*`

State-changing endpoints require authorization and governance checks.

## 17. Observability

Use structured JSON logging, OpenTelemetry-compatible tracing/metrics abstraction, correlation IDs, and health probes. Sensitive values are redacted before emission.

The health model distinguishes:

- process alive
- dependencies reachable
- dependencies trusted
- governance available
- evidence store writable
- audit chain valid
- production acceptance known

`/readyz` fails closed when mandatory production dependencies are unavailable or untrusted.

## 18. Error Handling

Errors are typed and mapped to stable error codes. Internal exceptions are never returned verbatim to untrusted clients. Security/governance failures do not fall back to permissive behavior.

Failure classes include:

- authentication
- authorization
- replay/freshness
- governance unavailable
- evidence insufficient
- provider unavailable
- dependency untrusted
- policy denied
- recovery denied
- persistence conflict
- integrity violation

## 19. Testing Strategy

Tests must include:

- unit tests for each subsystem
- persistence tests
- authorization/default-deny tests
- replay tests
- audit-chain tamper tests
- evidence contradiction tests
- jury independence tests
- counterfactual isolation tests
- digital-twin verification tests
- recovery approval tests
- incident containment tests
- capability-passport signature tests
- API integration tests
- adversarial malformed-input tests
- fail-closed dependency outage tests

No release claim is made from passing unit tests alone.

## 20. Deployment Model

One container image, one Python application. Production dependencies are injected through environment/configuration and secrets providers. The application must not embed cloud-specific credentials.

The modular monolith can later split into services only when scaling or trust-boundary evidence justifies it; interfaces are designed so extraction does not require rewriting core contracts.

## 21. Definition of Done

The unified build is complete when:

1. the package installs reproducibly;
2. one canonical entrypoint starts the API and core runtime;
3. all core subsystems above are implemented with real behavior;
4. persistence works locally and with PostgreSQL configuration;
5. the security/governance path defaults to deny;
6. audit chaining and passport verification detect tampering;
7. digital-twin state is observation-backed;
8. counterfactual execution cannot mutate production;
9. governed recovery respects approval requirements;
10. automated tests pass;
11. an SBOM/dependency scan workflow is defined;
12. runtime acceptance remains external evidence, not assumed by code;
13. ROAD/SIOS adapters fail closed when configured as mandatory;
14. no TODO/TBD/stub execution paths exist in the release package.

## 22. Explicit Non-Goals for First Unified Build

To keep the first production implementation coherent:

- no autonomous destructive remediation without explicit policy authority
- no invented external model/provider credentials
- no claim that external ROAD/SIOS services are healthy unless actually attested at runtime
- no direct cloud mutation adapters unless credentials and provider contracts are supplied
- no UI beyond the API/CLI in this build

These are boundaries, not placeholders: the interfaces support the capabilities while refusing unsafe or unverifiable execution.
