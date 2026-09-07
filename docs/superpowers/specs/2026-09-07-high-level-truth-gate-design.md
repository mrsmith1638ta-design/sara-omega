# SARA-OMEGA High-Level Truth Gate Design

## Purpose

Add a production-grade epistemic control layer above SARA-OMEGA's domain specialists and below final user-facing synthesis so no scientific, historical, engineering, or technical claim can leave the system with greater certainty than its evidence, scope, applicability, and provenance justify.

The objective is not to claim impossible omniscience. The enforceable guarantee is fail-closed certainty: when SARA cannot establish that a claim is universal, current, sourced, dimensionally valid, and applicable to the system under discussion, the claim must be downgraded, qualified, or blocked rather than emitted as an unqualified fact.

## Root Cause

The current science fabric carries provenance, evidence status, assumptions, limitations, source IDs, and validation status, but it lacks mandatory claim-scope and applicability semantics. This allows a result payload to expose design-dependent behavior as a simple boolean while a caveat is relegated to a limitation string.

Concrete examples in the current maglev layer include EDS values such as `active_control=False`, `passive_restoring_behavior=True`, and `low_speed_levitation=False`, and HTS values such as `passive_restoring_behavior=True`. Those can be valid for particular architectures or configurations, but are not universal statements across every implementation.

## Design Principle

**Certainty may only move downward unless stronger evidence is explicitly introduced.**

No provider, comparison helper, judge, Council member, or final synthesizer may promote a claim above the ceiling established by its provenance, applicability scope, evidence quality, dependency completeness, and validation state.

## Truth Gate Placement

The High-Level Truth Gate sits in the governed reasoning path after specialist analyses are normalized and before their claims are admitted to final synthesis. It also runs on the candidate final answer before Verdict signing and ledger persistence.

Logical flow:

1. User problem enters existing OMEGA lifecycle.
2. Domain specialists produce structured analyses.
3. Science analyses are normalized into structured claims.
4. **High-Level Truth Gate evaluates each claim.**
5. Council and judge receive only truth-gated claims plus explicit rejected/qualified claims.
6. Candidate synthesis is truth-gated again for overstatement or certainty promotion.
7. Only a truth-gate-passing Verdict may be signed and appended to the durable ledger.

The gate never grants execution authority. Existing `execution_authority=False` semantics for science remain unchanged.

## Claim Model

Introduce a focused claim model rather than overloading raw calculation results.

Each scientific/technical claim must include:

- `claim_text`: canonical claim statement.
- `provenance_class`: existing SARA provenance class.
- `evidence_status`: current evidence state.
- `applicability_scope`: one of:
  - `UNIVERSAL_LAW`
  - `FAMILY_LEVEL`
  - `ARCHITECTURE_SPECIFIC`
  - `CONFIGURATION_SPECIFIC`
  - `EXPERIMENTAL_OBSERVATION`
  - `HISTORICAL_DOCUMENTATION`
  - `HISTORICAL_RECONSTRUCTION`
  - `UNKNOWN`
- `certainty_level`: one of:
  - `VERIFIED`
  - `SUPPORTED`
  - `INFERRED`
  - `DISPUTED`
  - `UNVERIFIED`
  - `UNKNOWN`
- `dependency_conditions`: explicit conditions required for the claim to hold, for example geometry, guideway design, control architecture, speed regime, field topology, material, temperature, pressure, Reynolds/Mach regime, historical source, or date.
- `source_ids`: supporting source registry entries.
- `assumptions`: assumptions used to derive or apply the claim.
- `limitations`: known limitations.
- `validation_status`: current validation state.
- `universality_status`: one of:
  - `UNIVERSAL_SUPPORTED`
  - `SYSTEM_DEPENDENT`
  - `INSUFFICIENT_EVIDENCE`
  - `NOT_APPLICABLE`
- `certainty_ceiling`: highest user-facing certainty the claim may receive.

## Structured Engineering States

Replace misleading binary fields where engineering behavior is architecture-dependent.

For control, levitation, stability, or similar engineering properties, use structured values such as:

- `REQUIRED`
- `NOT_REQUIRED`
- `SYSTEM_DEPENDENT`
- `UNKNOWN`
- `NOT_APPLICABLE`

A boolean may remain only when the property is truly binary for the explicitly scoped system and the scope/dependencies are part of the same structured claim.

## High-Level Truth Gate Rules

The gate applies the following rules in order.

### 1. Evidence Rule

A claim without adequate evidence may not be emitted as `VERIFIED` or `SUPPORTED`. Missing or weak evidence downgrades the claim to `UNVERIFIED` or `UNKNOWN` and may produce `INSUFFICIENT_EVIDENCE`.

### 2. Applicability Rule

A claim scoped to a family, architecture, configuration, experiment, or reconstruction may not be rendered as universal. If the requested answer would require universal wording, the gate rewrites the status to `SYSTEM_DEPENDENT` or blocks the claim.

### 3. Dependency Rule

If required dependency conditions are unknown, the claim cannot be promoted beyond the certainty ceiling associated with the known inputs. The answer must name the missing dependencies when they materially affect correctness.

### 4. Provenance Rule

Provenance is monotonic. For example:

- `HISTORICALLY_COMPATIBLE_RECONSTRUCTION` may not become `DOCUMENTED_ANCIENT`.
- `ENGINEERING_MODEL` may not become `ESTABLISHED_PHYSICS`.
- `EXPERIMENTAL_TECHNOLOGY` may not become `DOCUMENTED_TECHNOLOGY` without independent evidence.
- `SIMULATION_OR_HYPOTHESIS` may not become an observed fact.

### 5. Numerical Rule

A numerical result requires:

- explicit inputs or clearly labeled defaults,
- units,
- dimensional consistency,
- equation provenance,
- assumption disclosure,
- validation status.

If user-provided inputs are absent, illustrative defaults must never be presented as user-specific calculations.

### 6. Temporal Rule

Claims whose truth may change over time must carry current-source evidence or be marked stale/currently unverified. The gate must not infer current deployment or maturity from historical evidence alone.

### 7. Historical Rule

Historical documentation, reconstruction, modern derivation, and numerical coincidence remain separate classes. Similar numbers or forms do not establish transmission, causation, authorship, chronology, or undocumented technology.

### 8. Final-Synthesis Rule

The candidate final answer is scanned for certainty promotion. If the prose says more than the structured claims support, the final answer is rejected for regeneration with a lower certainty level. If regeneration still fails, the system returns a governed uncertainty response rather than the overclaim.

## Domain-Specific Maglev Corrections

### EDS

Do not encode `active_control=False`, `passive_restoring_behavior=True`, or `low_speed_levitation=False` as universal family facts.

Represent these properties as system-dependent unless the problem identifies a specific EDS architecture with sufficient evidence. The claim must include dependencies such as guideway topology, onboard magnet architecture, damping method, transition speed, conductor/coil arrangement, and control strategy.

### HTS

Flux pinning is established superconducting physics, but transport-level passive restoring behavior is configuration-dependent. Claims must identify material, temperature, magnetic-field history, guideway configuration, geometry, and critical-current assumptions when relevant.

### EMS

Attractive electromagnetic suspension requiring active gap control may be treated as a documented characteristic of conventional EMS architectures, but wording must remain scoped to conventional EMS rather than every conceivable electromagnetic levitation system.

## Council and Judge Integration

The judge prompt and Council payload must receive:

- accepted claims,
- qualified claims,
- rejected claims,
- certainty ceilings,
- applicability scopes,
- dependency conditions,
- evidence gaps.

The judge is explicitly prohibited from promoting certainty because multiple providers agree. Provider count is not evidence independence.

If a Council member proposes a stronger statement than the gate permits, the statement is rejected or reduced before final synthesis.

## Failure Behavior

The High-Level Truth Gate is fail closed.

If a material claim cannot be validated, SARA must return a structured form of one of these outcomes:

- `SYSTEM_DEPENDENT`
- `INSUFFICIENT_EVIDENCE`
- `UNVERIFIED`
- `UNKNOWN`

The answer should still be useful: state what is known, what is unknown, what dependencies matter, and what evidence would be needed to strengthen the claim.

Truth-gate failure must not crash the service or bypass the existing OMEGA lifecycle. It results in a governed low-certainty Verdict.

## Audit and Ledger

Truth-gate decisions become part of the signed Verdict evidence trail. Persist at minimum:

- claim identifier or stable hash,
- original certainty,
- gated certainty,
- applicability scope,
- universality status,
- rejection/qualification reason,
- source IDs,
- validation result.

Do not add secrets, raw credentials, or sensitive internal configuration to the ledger.

## Test Strategy

Implementation is test-driven.

### Regression Tests

Create tests proving that EDS and HTS system-dependent properties are no longer exposed as universal booleans.

### Universality Tests

Examples that must fail closed or qualify:

- `All EDS maglev systems are passively stable.`
- `EDS never levitates at low speed.`
- `HTS levitation requires no active control.`
- `Every Doric column is seven diameters high.`
- `The Great Pyramid proves modern electromagnetic technology existed in ancient Egypt.`

### Provenance Tests

Verify that reconstruction, model, experiment, and hypothesis classes cannot be promoted to stronger factual classes.

### Numerical Tests

Verify user-supplied parameters override illustrative defaults and that defaults remain explicitly labeled when used.

### Final-Synthesis Tests

Feed the gate a candidate answer that intentionally overstates a scoped claim. The final-synthesis gate must reject or downgrade it.

### Adversarial Tests

Attempt certainty laundering through:

- provider consensus,
- confident wording,
- missing scope,
- omitted dependency fields,
- stale evidence,
- numerical coincidence,
- model-to-fact promotion,
- historical reconstruction-to-documentation promotion.

## Acceptance Criteria

The change is accepted only when all of the following are true:

1. Current maglev overgeneralization is reproduced by a failing regression test before implementation.
2. EDS and HTS architecture-dependent properties are represented with structured non-universal states.
3. The High-Level Truth Gate blocks or downgrades unsupported universality.
4. Provenance cannot be promoted by the gate, judge, or final synthesis.
5. Numerical outputs cannot masquerade illustrative defaults as user-specific results.
6. Truth-gate decisions are included in the governed Verdict evidence trail without secrets.
7. Existing OMEGA lifecycle, fail-safe, auth, signing, ledger, and `execution_authority=False` behavior remain intact.
8. Domain science tests pass.
9. Full repository test suite passes.
10. Existing adversarial gate passes.
11. CI passes on the exact branch commit proposed for merge.
12. Deployment, if authorized after merge, uses the exact verified commit SHA and is followed by live health and acceptance verification.

## Non-Goals

This change does not claim omniscience or literal 100% factual coverage of the world. It does not create a new execution plane, bypass authentication, replace the Council, or remove model reasoning. It constrains certainty and forces SARA to expose uncertainty when evidence is insufficient.

## Security and Governance Constraints

- No secret values may be printed, logged, committed, or added to test fixtures.
- No production credentials are required to implement or test this framework.
- No provider may gain execution authority through this change.
- Existing fail-safe and signing requirements remain mandatory.
- No majority-vote rule is introduced.
- Evidence quality and independence outrank provider count.
