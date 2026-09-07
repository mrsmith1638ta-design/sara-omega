# SARA-OMEGA High-Level Truth Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed High-Level Truth Gate that prevents SARA-OMEGA from expressing scientific, historical, engineering, or technical claims with more certainty or universality than their evidence, provenance, applicability, dependencies, and validation justify.

**Architecture:** Introduce structured claim/applicability models and a deterministic truth-gate evaluator in `app/science/`. Domain specialists emit scoped claims; the orchestrator truth-gates specialist analyses before judge/Council synthesis and gates the candidate synthesis before Verdict signing. Existing OMEGA lifecycle, signing, ledger, fail-safe, authentication, and `execution_authority=False` remain unchanged.

**Tech Stack:** Python 3, Pydantic, pytest, existing SARA-OMEGA orchestrator/provider architecture, GitHub Actions CI, Railway deployment after verified merge.

**Spec:** `docs/superpowers/specs/2026-09-07-high-level-truth-gate-design.md`

## Global Constraints

- Truth Gate is fail closed: unsupported certainty becomes `SYSTEM_DEPENDENT`, `INSUFFICIENT_EVIDENCE`, `UNVERIFIED`, or `UNKNOWN`.
- Certainty may only move downward unless stronger evidence is explicitly introduced.
- Provider agreement alone must never raise certainty.
- No secret values in code, tests, logs, Verdict evidence, or commits.
- Science retains `execution_authority=False`.
- Existing auth, fail-safe, signing, durable ledger, and OMEGA lifecycle remain mandatory.
- Deployment is only from an exact CI-verified merged commit SHA.

---

### Task 1: Structured truth-claim model and fail-closed evaluator

**Files:**
- Modify: `app/science/models.py`
- Create: `app/science/truth_gate.py`
- Create: `tests/science/test_truth_gate.py`

**Interfaces:**
- Produces `ApplicabilityScope`, `CertaintyLevel`, `UniversalityStatus`, `EngineeringState`, `ScienceClaim`, `TruthGateDecision`, and `HighLevelTruthGate.evaluate_claim()`.
- `ScienceClaim` carries provenance, evidence, applicability, certainty, dependencies, sources, assumptions, limitations, validation status, universality status, and certainty ceiling.
- `TruthGateDecision` records original/gated certainty, universality status, accepted/qualified/rejected state, and reasons.

- [ ] **Step 1: Write failing tests** proving a family-scoped EDS claim cannot be emitted as universal, missing dependencies force qualification, provenance cannot be promoted, and evidence gaps cap certainty.
- [ ] **Step 2: Run `pytest tests/science/test_truth_gate.py -v` and verify RED** because the new models/gate do not yet exist.
- [ ] **Step 3: Implement the minimal structured enums/models and deterministic evaluator** with monotonic certainty ordering (`VERIFIED > SUPPORTED > INFERRED > DISPUTED > UNVERIFIED > UNKNOWN`) and fail-closed qualification.
- [ ] **Step 4: Run `pytest tests/science/test_truth_gate.py -v` and verify GREEN.**
- [ ] **Step 5: Commit** `feat: add high-level truth claim gate`.

### Task 2: Correct EDS/HTS/EMS comparison semantics

**Files:**
- Modify: `app/science/comparison.py`
- Modify: `app/science/maglev_eds.py`
- Modify: `app/science/maglev_hts.py`
- Modify: `app/science/maglev_ems.py`
- Modify: `tests/science/test_maglev.py`
- Create: `tests/science/test_maglev_truth_scope.py`

**Interfaces:**
- Architecture-dependent properties use `EngineeringState` rather than unconditional booleans.
- EDS family-level `active_control`, passive restoring behavior, and low-speed levitation are `SYSTEM_DEPENDENT` unless a specific architecture supplies sufficient dependencies/evidence.
- HTS transport-level passive restoring behavior is scoped/configuration-dependent; flux pinning physics remains established.
- Conventional EMS active gap control remains documented but explicitly scoped to conventional EMS.

- [ ] **Step 1: Write regression tests** that fail on current `active_control=False`, `passive_restoring_behavior=True`, and `low_speed_levitation=False` universal EDS values and on unconditional transport-level HTS passive-restoring claims.
- [ ] **Step 2: Run focused maglev tests and verify RED.**
- [ ] **Step 3: Replace misleading binary family-level states with structured scope-aware values and explicit dependency metadata.**
- [ ] **Step 4: Run focused maglev tests and verify GREEN.**
- [ ] **Step 5: Commit** `fix: scope maglev engineering claims`.

### Task 3: Normalize specialist outputs into truth-gated claims

**Files:**
- Modify: `app/science/provider.py`
- Modify: `app/science/validation.py`
- Modify: `app/science/ancient_egypt.py`
- Modify: `app/science/classical_greek_roman.py`
- Modify: `app/science/engineering.py`
- Create: `tests/science/test_truth_gate_domains.py`

**Interfaces:**
- Produces `ScienceAnalysis.metadata["truth_gate"]` containing accepted, qualified, and rejected claim decisions.
- Historical reconstruction remains reconstruction; engineering models remain models; experimental technology cannot become documented technology.
- Numerical analyses distinguish supplied inputs from illustrative defaults.

- [ ] **Step 1: Write failing cross-domain tests** for Egyptian reconstruction, Doric ratio universalization, engineering defaults, and model-to-fact promotion.
- [ ] **Step 2: Run focused domain tests and verify RED.**
- [ ] **Step 3: Add normalization helpers that create `ScienceClaim` objects from domain outputs and run them through `HighLevelTruthGate`.**
- [ ] **Step 4: Run domain tests and verify GREEN.**
- [ ] **Step 5: Commit** `feat: truth-gate science specialist claims`.

### Task 4: Council/judge and final-synthesis certainty gate

**Files:**
- Modify: `app/orchestrator.py`
- Modify: `app/providers/openai_judge.py`
- Modify: `app/models.py`
- Create: `tests/science/test_truth_gate_orchestrator.py`
- Create: `tests/science/test_truth_gate_final_synthesis.py`

**Interfaces:**
- Council/judge payload receives accepted/qualified/rejected claims, certainty ceilings, applicability scopes, dependencies, and evidence gaps.
- Candidate final synthesis is checked against gated claims before signing.
- Overstated synthesis is downgraded/rejected; persistent overstatement yields governed uncertainty rather than an unqualified Verdict.
- Verdict exposes truth-gate evidence without secrets.

- [ ] **Step 1: Write failing integration tests** showing provider consensus cannot promote certainty and an overstated candidate answer is rejected/downgraded before signing.
- [ ] **Step 2: Run focused orchestrator tests and verify RED.**
- [ ] **Step 3: Integrate truth-gate payloads into orchestrator/judge and add final-synthesis certainty checks.**
- [ ] **Step 4: Run focused orchestrator tests and verify GREEN.**
- [ ] **Step 5: Commit** `feat: enforce truth gate in council synthesis`.

### Task 5: Adversarial and acceptance verification

**Files:**
- Create: `tests/science/test_truth_gate_adversarial.py`
- Modify: `docs/science/PROVENANCE.md`
- Modify: `docs/science/README.md`
- Modify: `BUILD_VERIFICATION.md`

**Interfaces:**
- Adversarial cases cover certainty laundering via consensus, confident wording, missing scope/dependencies, stale evidence, numerical coincidence, model-to-fact promotion, and reconstruction-to-documentation promotion.

- [ ] **Step 1: Add adversarial tests** for: `All EDS maglev systems are passively stable`, `EDS never levitates at low speed`, `HTS levitation requires no active control`, `Every Doric column is seven diameters high`, and `The Great Pyramid proves modern electromagnetic technology existed in ancient Egypt`.
- [ ] **Step 2: Run `pytest tests/science -v` and verify all science tests pass.**
- [ ] **Step 3: Run the full repository pytest suite, existing adversarial gate, compile checks, shell/Windows checks, and container build.**
- [ ] **Step 4: Inspect branch diff for secrets and unintended execution-authority/auth/fail-safe/signing changes.**
- [ ] **Step 5: Update documentation/build verification with exact evidence only, then commit** `docs: record truth gate verification`.

### Task 6: CI, merge, exact-commit Railway deployment, and live verification

**Files:**
- No production source changes after CI verification except review-requested fixes, which require rerunning verification.

**Interfaces:**
- Merge SHA is the only acceptable production source SHA.

- [ ] **Step 1: Open PR from `design/high-level-truth-gate-20260907` to `main`.**
- [ ] **Step 2: Require GitHub CI success on the exact final branch head.**
- [ ] **Step 3: Merge only after CI passes and record the exact merge SHA.**
- [ ] **Step 4: Deploy the exact merge SHA to Railway `sara-omega-council`; do not treat a generic redeploy of an older snapshot as release evidence.**
- [ ] **Step 5: Verify Railway deployment metadata commit SHA, `/health` HTTP 200, production acceptance, signer availability, `/data` persistence, and GPT Action schema availability.**
- [ ] **Step 6: Report exact verification evidence and explicitly state any remaining limitations; do not claim literal omniscience or universal 100% factual coverage.**
