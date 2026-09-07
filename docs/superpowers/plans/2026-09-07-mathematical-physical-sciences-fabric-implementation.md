# SARA-OMEGA Mathematical & Physical Sciences Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a governed Mathematical & Physical Sciences Fabric that adds Egyptian, Greek/Roman, modern engineering, EMS maglev, superconducting EDS, and HTS levitation reasoning to SARA-OMEGA without weakening the existing OMEGA Council, provenance rules, authentication, fail-safe, or signed durable ledger.

**Architecture:** Add modular science specialists under `app/science/` with a shared analysis contract, deterministic equation/source registries, unit and provenance validation, and a science router. Integrate them as evidence-producing specialists into the existing mandatory Council `solve` path; the Council remains final synthesis authority and all science output is reasoning-only.

**Tech Stack:** Python 3.12, Pydantic v2, pytest/pytest-asyncio, existing FastAPI gateway, existing OMEGA Council, SQLite durable ledger, Railway.

**Spec:** `docs/superpowers/specs/2026-09-07-mathematical-physical-sciences-fabric-design.md`

## Global Constraints

- SARA remains the orchestration and final-synthesis layer; science engines are specialists.
- Never convert a specialist result directly into verified fact.
- Historical evidence, reconstruction, modern engineering derivation, established physics, documented technology, experimental technology, and simulation/hypothesis remain distinct.
- Every calculation carries units, assumptions, provenance class, evidence status, confidence, limitations, and validation state.
- No science engine receives execution authority.
- The existing OMEGA Council lifecycle, governance, fail-safe, authentication, signed durable verdict ledger, and rollback posture remain intact.
- Current/time-sensitive technology claims require source freshness; static equations and curated historical facts may be local registry data.
- No secrets in source control.

---

### Task 1: Common Science Contracts and Validation

**Files:**
- Create: `app/science/__init__.py`
- Create: `app/science/models.py`
- Create: `app/science/units.py`
- Create: `app/science/validation.py`
- Test: `tests/science/test_models_units_validation.py`

**Interfaces:**
- Produces `ProvenanceClass`, `ScienceEvidenceStatus`, `ScienceCalculation`, `ScienceAnalysis`, `validate_dimensions()`, and bounded validation errors for all later tasks.

- [ ] **Step 1: Write failing tests** covering provenance enum values, bounded serializable analysis objects, unit compatibility, invalid negative/zero inputs, and dimensional mismatch.
- [ ] **Step 2: Run** `pytest tests/science/test_models_units_validation.py -v` and confirm RED.
- [ ] **Step 3: Implement minimal contracts and validators.** `ScienceCalculation` must include equation id, variables, units, inputs, result, provenance class, evidence status, assumptions, limitations, source ids, and validation status. `ScienceAnalysis` must include domain, summary, calculations, evidence gaps, confidence, and `execution_authority=False`.
- [ ] **Step 4: Run focused tests and confirm GREEN.**
- [ ] **Step 5: Commit** `feat: add science analysis contracts and validation`.

### Task 2: Curated Equation and Source Registry

**Files:**
- Create: `app/science/registry.py`
- Create: `data/science/equations/core.json`
- Create: `data/science/sources/core.json`
- Test: `tests/science/test_registry.py`

**Interfaces:**
- Produces `ScienceRegistry`, `get_equation(id)`, `get_source(id)`, and registry validation consumed by domain engines.

- [ ] **Step 1: Write failing tests** for duplicate IDs, missing source references, invalid provenance, dimensional schema errors, and required metadata.
- [ ] **Step 2: Run focused registry tests and confirm RED.**
- [ ] **Step 3: Add curated records** for Egyptian seked, Egyptian frustum volume, Euclidean/Pythagorean geometry, Vitruvian proportional relationships, drag force/power, state-space control, simplified EMS force model with approximation caveat, EDS lift/drag metadata, and HTS flux-pinning model metadata. Include only claims supportable by the approved provenance classes; no claim that a surviving Old Kingdom source gives the exact Giza construction formula.
- [ ] **Step 4: Implement registry loading and fail-closed validation.**
- [ ] **Step 5: Run tests and commit** `feat: add governed science equation registry`.

### Task 3: Ancient Egyptian and Greek/Roman Engines

**Files:**
- Create: `app/science/ancient_egypt.py`
- Create: `app/science/classical_greek_roman.py`
- Test: `tests/science/test_ancient_classical.py`

**Interfaces:**
- Produces `AncientEgyptEngine.analyze(problem)` and `ClassicalGreekRomanEngine.analyze(problem)` returning `ScienceAnalysis`.

- [ ] **Step 1: Write failing tests** for 440/280 cubit seked = 5.5 palms, modern face-angle derivation tagged `MODERN_ENGINEERING_DERIVATION`, frustum volume, Egyptian unit conversion, Vitruvian ratio calculations, Roman arch/column calculations, and rejection of unsupported “secret pyramid formula” assertions.
- [ ] **Step 2: Run focused tests and confirm RED.**
- [ ] **Step 3: Implement deterministic calculation methods** with explicit provenance labels and source ids. Treat Giza use of the 5.5-palm seked as historically compatible reconstruction unless direct evidence is supplied.
- [ ] **Step 4: Run tests and confirm GREEN.**
- [ ] **Step 5: Commit** `feat: add ancient and classical construction math engines`.

### Task 4: Modern Engineering Physics Engine

**Files:**
- Create: `app/science/engineering.py`
- Test: `tests/science/test_engineering.py`

**Interfaces:**
- Produces `EngineeringPhysicsEngine.analyze(problem)` for deterministic geometry, statics, tolerance, drag, power, and state-space calculations.

- [ ] **Step 1: Write failing tests** for geometry invariants, equilibrium checks, drag scaling with `v^2`, aerodynamic power scaling with `v^3`, uncertainty/tolerance propagation, and invalid-unit rejection.
- [ ] **Step 2: Run and confirm RED.**
- [ ] **Step 3: Implement minimal engineering helpers** with SI-normalized inputs and clear limitations. Do not claim professional certification or site-specific structural approval.
- [ ] **Step 4: Run and confirm GREEN.**
- [ ] **Step 5: Commit** `feat: add modern engineering physics engine`.

### Task 5: EMS, EDS, and HTS Levitation Engines

**Files:**
- Create: `app/science/maglev_ems.py`
- Create: `app/science/maglev_eds.py`
- Create: `app/science/maglev_hts.py`
- Create: `app/science/comparison.py`
- Test: `tests/science/test_maglev.py`

**Interfaces:**
- Produces `EMSMaglevEngine`, `EDSMaglevEngine`, `HTSMaglevEngine`, and `compare_levitation_systems()`.

- [ ] **Step 1: Write failing tests** for EMS air-gap/current-domain validation, drag/power calculations at speed, EDS speed-dependent classification, HTS temperature/critical-current validation, and comparison output that distinguishes active-control burden, passive stability, low-speed/high-speed behavior, thermal constraints, maturity, and guideway requirements.
- [ ] **Step 2: Run and confirm RED.**
- [ ] **Step 3: Implement bounded analytical models** and label simplified force models as `ENGINEERING_MODEL`, documented system facts as `DOCUMENTED_TECHNOLOGY`, laboratory HTS claims as `EXPERIMENTAL_TECHNOLOGY`, and speculative cases as `SIMULATION_OR_HYPOTHESIS`.
- [ ] **Step 4: Run and confirm GREEN.**
- [ ] **Step 5: Commit** `feat: add EMS EDS and HTS levitation engines`.

### Task 6: Science Router and OMEGA Council Integration

**Files:**
- Create: `app/science/router.py`
- Modify: `app/orchestrator.py`
- Modify: `app/providers/openai_judge.py`
- Test: `tests/science/test_router_council_integration.py`

**Interfaces:**
- Produces selective `ScienceRouter.route(problem)` and injects science analyses into the existing Council evidence payload without bypassing mandatory stages.

- [ ] **Step 1: Write failing integration tests** proving Egyptian/Greek/Roman queries select only relevant science engines; maglev queries select EMS/EDS/HTS as appropriate; unrelated everyday queries do not fan out to all science engines; `council=false` cannot bypass Council; science results are advisory and `execution_authority=False`.
- [ ] **Step 2: Run and confirm RED.**
- [ ] **Step 3: Integrate science routing into `SaraOmega.solve`** after problem mapping/governance evaluation and before cross-examination. Convert science analyses into bounded specialist/evidence entries with provenance metadata. Extend the judge prompt to respect science provenance classes and never treat consensus as verification.
- [ ] **Step 4: Run focused Council integration tests and existing orchestrator tests.**
- [ ] **Step 5: Commit** `feat: integrate science fabric into OMEGA Council`.

### Task 7: Custom GPT Gateway and Consumer Output

**Files:**
- Modify: `main.py`
- Modify: `chatgpt-gpt-action.yaml`
- Test: `tests/science/test_gpt_science_gateway.py`

**Interfaces:**
- Existing `solve` operation remains the only consumer path; responses expose concise science summary, equations/calculations, provenance class, epistemic status, confidence, limitations, and Council integrity state.

- [ ] **Step 1: Write failing gateway tests** for Egyptian math, Roman architecture, and maglev comparison prompts through the existing authenticated `solve` operation; verify no unrestricted science bypass endpoint exists.
- [ ] **Step 2: Run and confirm RED.**
- [ ] **Step 3: Extend response/schema metadata only as needed** so science analyses are visible through the governed verdict while preserving existing auth/rate/fail-safe controls.
- [ ] **Step 4: Run gateway, schema, auth, fail-safe, and Council regression tests.**
- [ ] **Step 5: Commit** `feat: expose governed science fabric to SARA Custom GPT`.

### Task 8: Adversarial, Provenance, and Full Regression Gate

**Files:**
- Create: `tests/science/test_science_adversarial.py`
- Modify: `BUILD_VERIFICATION.md`

**Interfaces:**
- Produces final release evidence only; no new runtime interface.

- [ ] **Step 1: Add adversarial tests** for forged historical attribution, numerology injection, unsupported pyramid secrets, invalid units, impossible magnetic inputs, current-technology claims with stale evidence, provider consensus without evidence, Council bypass, and execution-authority escalation.
- [ ] **Step 2: Run** `pytest tests/science -v` and fix failures without weakening governance.
- [ ] **Step 3: Run full suite** `pytest -q`, Python compile checks, repository adversarial gate, and Docker build.
- [ ] **Step 4: Inspect diff for secrets and unsupported historical assertions.**
- [ ] **Step 5: Update `BUILD_VERIFICATION.md` with measured results only and commit** `test: verify mathematical physical sciences fabric`.

### Task 9: Review, Merge, and Exact-Commit Railway Deployment

**Files:**
- No code changes unless review finds defects.

**Interfaces:**
- Produces merged main SHA and live Railway deployment evidence.

- [ ] **Step 1: Create a PR from the implementation branch to `main` and inspect the full diff against the approved spec.**
- [ ] **Step 2: Require green CI on the exact head commit; fix any failures through normal TDD.**
- [ ] **Step 3: Merge only the verified commit to `main`.**
- [ ] **Step 4: Deploy the exact merged SHA to the existing live `sara-omega-council` Railway service; do not create a duplicate production endpoint. Preserve the old rollback service.**
- [ ] **Step 5: Verify live `/health`, production acceptance, exact commit, volume persistence, signer health/connectivity, and authenticated Custom GPT `solve` behavior when the platform allows a credential-safe smoke test. If authenticated smoke is blocked by platform credential policy, report that limitation rather than claiming it ran.**
- [ ] **Step 6: Confirm the primary domain `sara-omega-production.up.railway.app` still routes to the science-enabled Council deployment and returns HTTP 200.**

## Plan Self-Review

- Spec coverage: all four science engines, provenance taxonomy, source/equation registries, Custom GPT path, Council integration, fail-closed behavior, security boundaries, tests, and deployment gates are assigned to tasks.
- Placeholder scan: no TBD/TODO/implementation-later placeholders remain.
- Type consistency: all domain engines return `ScienceAnalysis`; router consumes those objects; Council and gateway use the existing governed `solve` path.
