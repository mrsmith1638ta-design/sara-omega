# SARA OMEGA ChatGPT V3.4.0 Riemann Research Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the governed SARA OMEGA ChatGPT V3.4.0 Riemann Research Engine so SARA can encode, compute, and adversarially gate RH-equivalent research claims without promoting numerical evidence or candidate lemmas into proof.

**Architecture:** Add a focused `app/science/riemann/` package with proof-status models, arithmetic helpers, Baez-Duarte/Vasyunin/Selberg computations, Mellin scan utilities, and a deterministic proof gate. Integrate it through the existing science provider/router/truth-gate path and add a GitHub validation hook that runs the Riemann adversarial tests.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing SARA OMEGA science contracts, existing OMEGA Council and High-Level Truth Gate.

**Spec:** `docs/superpowers/specs/2026-09-19-riemann-research-engine-v340-design.md`

## Global Constraints

- SARA OMEGA remains the final synthesis and governance layer.
- The Riemann engine is a research specialist and has no execution authority.
- Every Riemann result must carry one of `NUMERICAL_EVIDENCE`, `SYMBOLIC_IDENTITY`, `CANDIDATE_LEMMA`, or `FORMAL_PROOF_CERTIFIED`.
- Only `FORMAL_PROOF_CERTIFIED` may support user-facing proof language.
- Finite computation, numerical convergence, Mellin-frequency structure, determinant-ratio behavior, and quantum/dilation interpretation cannot certify RH.
- Proof routes must fail closed on circular RH assumptions or assumptions equivalent to RH.
- Existing SARA OMEGA governance, authority, science truth-gate, ledger, and deployment gates must not be weakened.
- Preserve unrelated workspace changes, including the existing untracked `tools/offline_sara_public_plugin_validation.py`.

## Review Focus

- Finite-to-infinite extrapolation: tested `N <= M` must remain `NUMERICAL_EVIDENCE`.
- Circular assumptions: text containing RH, equivalent zero-free claims, or "assuming all zeros" must be rejected as proof routes.
- Proof-status promotion: provider consensus or judge synthesis must not convert a candidate lemma into a proof.
- Numerical stability: Gram matrix helpers must handle singular/ill-conditioned small examples with bounded failures.
- Router scope: ordinary science/math prompts must not fan out to the Riemann engine unless RH/Nyman-Beurling/Vasyunin/zeta/Mobius language is present.

---

### Task 1: Riemann Proof-Status Models

**Files:**
- Create: `app/science/riemann/__init__.py`
- Create: `app/science/riemann/models.py`
- Test: `tests/science/test_riemann_models.py`

**Interfaces:**
- Produces: `RiemannProofStatus`, `RiemannRoute`, `RiemannResult`, `RiemannComputationFailure`, and `classify_user_facing_strength(result: RiemannResult) -> str`.
- Consumes: Pydantic v2 and existing Python enum patterns from `app/science/models.py`.

- [ ] **Step 1: Write the failing proof-status tests**

```python
from app.science.riemann.models import (
    RiemannProofStatus,
    RiemannResult,
    classify_user_facing_strength,
)


def test_only_formal_certificate_supports_proof_language():
    numerical = RiemannResult(
        statement="d_N decreased for tested N",
        status=RiemannProofStatus.NUMERICAL_EVIDENCE,
        evidence=["N=20 finite computation"],
    )
    certified = RiemannResult(
        statement="A certified theorem statement",
        status=RiemannProofStatus.FORMAL_PROOF_CERTIFIED,
        evidence=["lean:theorem_id"],
        certificate_id="lean:theorem_id",
    )

    assert classify_user_facing_strength(numerical) == "observed for tested finite cases"
    assert classify_user_facing_strength(certified) == "formal proof certified"
```

- [ ] **Step 2: Run the focused RED test**

Run: `pytest -q tests/science/test_riemann_models.py`

Expected: FAIL with `ModuleNotFoundError` or missing symbols from `app.science.riemann.models`.

- [ ] **Step 3: Implement minimal models**

Implement:

```python
class RiemannProofStatus(str, Enum):
    NUMERICAL_EVIDENCE = "NUMERICAL_EVIDENCE"
    SYMBOLIC_IDENTITY = "SYMBOLIC_IDENTITY"
    CANDIDATE_LEMMA = "CANDIDATE_LEMMA"
    FORMAL_PROOF_CERTIFIED = "FORMAL_PROOF_CERTIFIED"
```

`RiemannResult` fields:

- `statement: str`
- `status: RiemannProofStatus`
- `evidence: list[str] = []`
- `assumptions: list[str] = []`
- `limitations: list[str] = []`
- `certificate_id: str | None = None`
- `metadata: dict[str, Any] = {}`

`RiemannResult` must reject `FORMAL_PROOF_CERTIFIED` without `certificate_id`.

- [ ] **Step 4: Run GREEN verification**

Run: `pytest -q tests/science/test_riemann_models.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/science/riemann tests/science/test_riemann_models.py
git commit -m "feat: add Riemann proof status models"
```

### Task 2: Arithmetic Helpers and Selberg Coefficients

**Files:**
- Create: `app/science/riemann/mobius.py`
- Create: `app/science/riemann/selberg.py`
- Test: `tests/science/test_riemann_arithmetic.py`

**Interfaces:**
- Consumes: `RiemannResult`, `RiemannProofStatus`.
- Produces: `mobius_values(n: int) -> list[int]`, `chebyshev_psi_values(n: int) -> list[float]`, `selberg_coefficients(N: int) -> list[float]`, `theta_N(N: int) -> float`, and `finite_psi_N(N: int, y: int) -> float`.

- [ ] **Step 1: Write failing tests for exact small values**

```python
import math

from app.science.riemann.mobius import mobius_values
from app.science.riemann.selberg import finite_psi_N, selberg_coefficients


def test_mobius_values_match_small_known_sequence():
    assert mobius_values(10) == [1, -1, -1, 0, -1, 1, -1, 0, 0, 1]


def test_selberg_coefficients_have_zero_at_n_equal_N():
    coeffs = selberg_coefficients(8)
    assert math.isclose(coeffs[7], 0.0, abs_tol=1e-12)
    assert coeffs[0] == -1.0


def test_finite_psi_N_matches_classical_range_identity_for_small_y():
    # For y <= N, psi_N(y) should match psi(y) via the divisor identities.
    assert math.isclose(finite_psi_N(10, 1), 0.0, abs_tol=1e-12)
    assert math.isclose(finite_psi_N(10, 2), math.log(2), rel_tol=1e-12)
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/science/test_riemann_arithmetic.py`

Expected: FAIL due to missing modules.

- [ ] **Step 3: Implement deterministic arithmetic**

Use direct trial division for `mobius_values` because CI test sizes are small. `finite_psi_N` must implement:

```text
psi_N(y) = -log(N)
           + log(N) * sum_{n<=N} mu(n) floor(y/n)
           - sum_{n<=N} mu(n) log(n) floor(y/n)
```

`selberg_coefficients(N)` must return:

```text
c_n(N) = -mu(n) * (1 - log(n) / log(N))
```

for `1 <= n <= N`.

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/science/test_riemann_arithmetic.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/science/riemann/mobius.py app/science/riemann/selberg.py tests/science/test_riemann_arithmetic.py
git commit -m "feat: add Riemann arithmetic helpers"
```

### Task 3: Baez-Duarte Route Encoding and J_N Split

**Files:**
- Create: `app/science/riemann/baez_duarte.py`
- Modify: `app/science/riemann/selberg.py`
- Test: `tests/science/test_riemann_baez_duarte.py`

**Interfaces:**
- Consumes: arithmetic helpers from Task 2.
- Produces: `riemann_sufficient_target() -> RiemannRoute`, `error_norm_identity_record(N: int) -> RiemannResult`, and `split_J_target(N: int) -> RiemannResult`.

- [ ] **Step 1: Write failing tests for status and target shape**

```python
from app.science.riemann.baez_duarte import (
    error_norm_identity_record,
    riemann_sufficient_target,
    split_J_target,
)
from app.science.riemann.models import RiemannProofStatus


def test_sufficient_target_is_candidate_lemma_not_proof():
    route = riemann_sufficient_target()
    assert route.status == RiemannProofStatus.CANDIDATE_LEMMA
    assert "J_N = o(log^2 N)" in route.statement
    assert "Baez-Duarte" in " ".join(route.evidence)


def test_error_identity_is_symbolic_identity():
    result = error_norm_identity_record(20)
    assert result.status == RiemannProofStatus.SYMBOLIC_IDENTITY
    assert "theta_N^2 / log^2(N)" in result.statement


def test_J_split_is_not_promoted_to_bound():
    result = split_J_target(20)
    assert result.status == RiemannProofStatus.SYMBOLIC_IDENTITY
    assert "tail" in result.statement.lower()
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/science/test_riemann_baez_duarte.py`

Expected: FAIL due to missing route functions.

- [ ] **Step 3: Implement route records**

`riemann_sufficient_target()` must state:

```text
theta_N = O(1) and J_N = o(log^2 N) would force ||e_N||_2 -> 0 and hence RH through the Baez-Duarte/Nyman-Beurling criterion.
```

It must include limitation:

```text
This is an RH-equivalent proof target, not an unconditional proof.
```

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/science/test_riemann_baez_duarte.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/science/riemann/baez_duarte.py app/science/riemann/selberg.py tests/science/test_riemann_baez_duarte.py
git commit -m "feat: encode Baez-Duarte Riemann proof target"
```

### Task 4: Vasyunin Gram Matrix and Optimizer Computations

**Files:**
- Create: `app/science/riemann/vasyunin.py`
- Test: `tests/science/test_riemann_vasyunin.py`

**Interfaces:**
- Produces: `rho(n: int, x: float) -> float`, `gram_entry(j: int, k: int, samples: int = 4096) -> float`, `gram_matrix(N: int, samples: int = 4096) -> list[list[float]]`, `target_vector(N: int, samples: int = 4096) -> list[float]`, `optimizer_coefficients(N: int, samples: int = 4096) -> list[float]`, `mobius_residual(N: int, samples: int = 4096) -> RiemannResult`, and `schur_decrement_record(N: int) -> RiemannResult`.
- Consumes: `numpy` only if already available; otherwise use pure Python for small CI sizes. If adding `numpy` is necessary, update `pyproject.toml` and requirements in the same task.

- [ ] **Step 1: Write failing tests for structural properties**

```python
import math

from app.science.riemann.models import RiemannProofStatus
from app.science.riemann.vasyunin import gram_matrix, mobius_residual, rho


def test_rho_fractional_part_definition():
    assert math.isclose(rho(2, 0.2), 0.5, abs_tol=1e-12)
    assert math.isclose(rho(3, 0.25), (1 / 0.75) % 1, abs_tol=1e-12)


def test_gram_matrix_is_symmetric_for_small_N():
    G = gram_matrix(3, samples=512)
    assert len(G) == 3
    assert all(len(row) == 3 for row in G)
    for i in range(3):
        for j in range(3):
            assert math.isclose(G[i][j], G[j][i], rel_tol=1e-9, abs_tol=1e-9)


def test_mobius_residual_is_numerical_evidence():
    result = mobius_residual(4, samples=512)
    assert result.status == RiemannProofStatus.NUMERICAL_EVIDENCE
    assert "r_N" in result.statement
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/science/test_riemann_vasyunin.py`

Expected: FAIL due to missing module.

- [ ] **Step 3: Implement bounded numerical helpers**

Implement midpoint quadrature over `x in (0, 1)` for CI-safe tests. Use explicit `RiemannComputationFailure` when `N < 1`, `samples < 16`, or a linear solve is singular.

Do not label any finite result above `NUMERICAL_EVIDENCE`.

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/science/test_riemann_vasyunin.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/science/riemann/vasyunin.py tests/science/test_riemann_vasyunin.py
git commit -m "feat: add Vasyunin Gram research computations"
```

### Task 5: Mellin/Smooth Spectral Research Utilities

**Files:**
- Create: `app/science/riemann/spectral.py`
- Test: `tests/science/test_riemann_spectral.py`

**Interfaces:**
- Consumes: Gram matrices and `RiemannResult`.
- Produces: `mellin_pair(N: int, t: float) -> list[tuple[float, float]]`, `frequency_scan_record(N: int, t_values: list[float]) -> RiemannResult`, and `smooth_basis_labels() -> list[str]`.

- [ ] **Step 1: Write failing tests for blind scan status**

```python
from app.science.riemann.models import RiemannProofStatus
from app.science.riemann.spectral import frequency_scan_record, mellin_pair


def test_mellin_pair_uses_log_frequency_modes():
    pair = mellin_pair(3, 2.0)
    assert len(pair) == 3
    assert pair[0][0] == 1.0
    assert pair[0][1] == 0.0


def test_frequency_scan_is_numerical_evidence_only():
    result = frequency_scan_record(10, [0.5, 1.0, 2.0])
    assert result.status == RiemannProofStatus.NUMERICAL_EVIDENCE
    assert "blind" in " ".join(result.limitations).lower()
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/science/test_riemann_spectral.py`

Expected: FAIL due to missing module.

- [ ] **Step 3: Implement lightweight scan records**

For V3.4.0 CI, this task records scan structure and computes mode columns only. Full dense Schur complement energy scans may be added later behind bounded size guards.

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/science/test_riemann_spectral.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/science/riemann/spectral.py tests/science/test_riemann_spectral.py
git commit -m "feat: add Mellin spectral research records"
```

### Task 6: Riemann Proof Gate and Truth-Gate Extension

**Files:**
- Create: `app/science/riemann/proof_gate.py`
- Modify: `app/science/truth_gate.py`
- Test: `tests/science/test_riemann_proof_gate.py`

**Interfaces:**
- Produces: `RiemannProofGate.evaluate(text: str, result: RiemannResult | None = None) -> dict[str, object]`.
- Consumes: `HighLevelTruthGate.evaluate_text_claim`.

- [ ] **Step 1: Write failing adversarial proof-gate tests**

```python
from app.science.riemann.models import RiemannProofStatus, RiemannResult
from app.science.riemann.proof_gate import RiemannProofGate
from app.science.truth_gate import HighLevelTruthGate


def test_rejects_finite_computation_as_RH_proof():
    result = RiemannResult(
        statement="d_N decreased for N <= 200, therefore RH is proved",
        status=RiemannProofStatus.NUMERICAL_EVIDENCE,
        evidence=["finite scan"],
    )
    gate = RiemannProofGate().evaluate(result.statement, result)
    assert gate["allowed_as_proof"] is False
    assert "finite" in " ".join(gate["reasons"]).lower()


def test_rejects_hidden_RH_assumption():
    gate = RiemannProofGate().evaluate("Assume RH and prove the Vasyunin bound.")
    assert gate["allowed_as_proof"] is False
    assert "circular" in " ".join(gate["reasons"]).lower()


def test_high_level_truth_gate_qualifies_RH_proof_claim():
    verdict = HighLevelTruthGate().evaluate_text_claim("SARA has proved RH using quantum Mellin modes.")
    assert verdict["allowed_as_unqualified_fact"] is False
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/science/test_riemann_proof_gate.py`

Expected: FAIL due to missing proof gate or missing truth-gate RH detection.

- [ ] **Step 3: Implement deterministic forbidden-claim checks**

Reject proof language when text includes combinations of:

- `riemann hypothesis`, `RH`, or `zeta`;
- `proved`, `proof`, `qed`, `solved`, or `certified`;
- finite evidence markers such as `N <=`, `tested`, `scan`, `numerical`, `observed`;
- circular markers such as `assume RH`, `assuming the Riemann Hypothesis`, `all zeros lie on`, or `zero-free line`.

Truth gate extension must return `SYSTEM_DEPENDENT`, `INSUFFICIENT_EVIDENCE`, or `UNVERIFIED`, never unqualified acceptance, for uncertified RH proof text.

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/science/test_riemann_proof_gate.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/science/riemann/proof_gate.py app/science/truth_gate.py tests/science/test_riemann_proof_gate.py
git commit -m "feat: add Riemann proof adversarial gate"
```

### Task 7: Science Provider and Router Integration

**Files:**
- Create: `app/science/riemann/provider.py`
- Modify: `app/science/provider.py`
- Modify: `app/science/router.py`
- Modify: `app/orchestrator.py`
- Test: `tests/science/test_riemann_integration.py`

**Interfaces:**
- Produces: `RiemannResearchEngine.analyze(problem: str) -> ScienceAnalysis`.
- Consumes: existing `ScienceSpecialist`, `ScienceAnalysis`, `ScienceCalculation`, `HighLevelTruthGate`, and provider result format.

- [ ] **Step 1: Write failing integration tests**

```python
import pytest

from app.models import Assignment, Problem
from app.router import OmegaRouter
from app.science.provider import ScienceSpecialist


def test_router_selects_riemann_engine_for_RH_query():
    providers = [a.provider for a in OmegaRouter().route(Problem(query="Analyze the Riemann Hypothesis J_N target."), None)]
    assert "science_riemann" in providers


@pytest.mark.asyncio
async def test_riemann_provider_returns_advisory_science_analysis():
    result = await ScienceSpecialist("science_riemann").run(
        Assignment(provider="science_riemann", role="research", task="Explain theta_N and J_N for RH")
    )
    analysis = result.raw["science_analysis"]
    assert result.success is True
    assert analysis["domain"] == "riemann_hypothesis"
    assert analysis["execution_authority"] is False
    assert analysis["metadata"]["proof_status"] != "FORMAL_PROOF_CERTIFIED"
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/science/test_riemann_integration.py`

Expected: FAIL because router/provider do not know `science_riemann`.

- [ ] **Step 3: Implement provider integration**

Add `science_riemann` to:

- `app/science/provider.py` engine map;
- `app/router.py` science provider mapping;
- `app/science/router.py` keyword routing.

`RiemannResearchEngine.analyze()` should return a bounded `ScienceAnalysis` containing symbolic route records and adversarial limitations, not a claimed proof.

- [ ] **Step 4: Run GREEN plus existing science router tests**

Run:

```bash
pytest -q tests/science/test_riemann_integration.py tests/science/test_router_council_integration.py tests/test_router.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/science/riemann/provider.py app/science/provider.py app/science/router.py app/orchestrator.py tests/science/test_riemann_integration.py
git commit -m "feat: integrate Riemann research engine with SARA science routing"
```

### Task 8: Registry Data and Documentation

**Files:**
- Create: `data/science/equations/riemann.json`
- Create: `data/science/sources/riemann.json`
- Modify: `app/science/registry.py`
- Create: `docs/science/RIEMANN_RESEARCH_ENGINE.md`
- Test: `tests/science/test_riemann_registry.py`

**Interfaces:**
- Consumes: existing `ScienceRegistry` conventions.
- Produces: loadable Riemann equation/source records and user-facing internal documentation.

- [ ] **Step 1: Write failing registry tests**

```python
from app.science.registry import ScienceRegistry


def test_riemann_registry_records_load():
    registry = ScienceRegistry.default()
    assert registry.get_equation("riemann.baez_duarte_distance")["domain"] == "riemann_hypothesis"
    assert registry.get_equation("riemann.J_N_bottleneck")["provenance_class"] == "MODERN_ENGINEERING_DERIVATION"
    assert registry.get_source("riemann.local.v340_spec")["evidence_status"] == "UNVERIFIED"
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/science/test_riemann_registry.py`

Expected: FAIL because default registry only loads `core.json`.

- [ ] **Step 3: Extend registry loading safely**

Update `ScienceRegistry.default()` to load `core.json` plus optional domain JSON files under `data/science/equations/*.json` and `data/science/sources/*.json`, while preserving duplicate-ID rejection.

Add Riemann records for:

- `riemann.baez_duarte_distance`
- `riemann.mobius_correction`
- `riemann.J_N_bottleneck`
- `riemann.vasyunin_schur_decrement`
- `riemann.mellin_mode_scan`

Use `MODERN_ENGINEERING_DERIVATION` or `SIMULATION_OR_HYPOTHESIS` according to existing enum constraints, and explain in documentation that this taxonomy is reused as SARA's current science provenance vocabulary.

- [ ] **Step 4: Run GREEN**

Run:

```bash
pytest -q tests/science/test_riemann_registry.py tests/science/test_registry.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data/science/equations/riemann.json data/science/sources/riemann.json app/science/registry.py docs/science/RIEMANN_RESEARCH_ENGINE.md tests/science/test_riemann_registry.py
git commit -m "docs: register Riemann research engine sources"
```

### Task 9: GitHub Adversarial Validation Gate

**Files:**
- Create: `tests/science/test_riemann_adversarial.py`
- Modify: `.github/workflows/sara-v32-validate.yml`
- Modify: `BUILD_VERIFICATION.md`

**Interfaces:**
- Produces: CI enforcement only; no runtime interface.

- [ ] **Step 1: Write adversarial tests**

```python
from app.science.riemann.models import RiemannProofStatus, RiemannResult
from app.science.riemann.proof_gate import RiemannProofGate


def test_provider_consensus_cannot_certify_RH():
    result = RiemannResult(
        statement="Three providers agree RH is solved.",
        status=RiemannProofStatus.CANDIDATE_LEMMA,
        evidence=["provider:a", "provider:b", "provider:c"],
    )
    decision = RiemannProofGate().evaluate("Providers agree RH is proved.", result)
    assert decision["allowed_as_proof"] is False


def test_quantum_interpretation_cannot_certify_RH():
    decision = RiemannProofGate().evaluate("The dilation Hamiltonian spectrum proves RH.")
    assert decision["allowed_as_proof"] is False


def test_formal_certificate_required_for_proof_status():
    try:
        RiemannResult(statement="RH proof", status=RiemannProofStatus.FORMAL_PROOF_CERTIFIED)
    except ValueError as exc:
        assert "certificate" in str(exc).lower()
    else:
        raise AssertionError("formal proof without certificate accepted")
```

- [ ] **Step 2: Run RED or confirm existing gate already catches some cases**

Run: `pytest -q tests/science/test_riemann_adversarial.py`

Expected: FAIL until Task 6 implementation exists; after Task 6, PASS.

- [ ] **Step 3: Wire CI**

Update `.github/workflows/sara-v32-validate.yml` to include:

```yaml
- name: Riemann research adversarial gate
  run: pytest -q tests/science/test_riemann_*.py
```

Keep the existing V3.2 workflow name if renaming would disrupt deployment, but add a comment or step label that this covers V3.4.0 Riemann validation.

- [ ] **Step 4: Run local gate**

Run:

```bash
pytest -q tests/science/test_riemann_*.py
python tools/adversarial_gate.py
```

Expected: all Riemann tests pass; adversarial gate prints JSON with all checks passing.

- [ ] **Step 5: Update measured verification**

Update `BUILD_VERIFICATION.md` with measured commands and results only. If full `pytest -q` is too slow or environment-blocked, record the exact limitation and run focused suites.

- [ ] **Step 6: Commit**

```bash
git add tests/science/test_riemann_adversarial.py .github/workflows/sara-v32-validate.yml BUILD_VERIFICATION.md
git commit -m "test: add Riemann research adversarial validation gate"
```

### Task 10: Full Verification and Review

**Files:**
- No new runtime files unless verification reveals a defect.

**Interfaces:**
- Produces: final evidence that the V3.4.0 Riemann engine is integrated and guarded.

- [ ] **Step 1: Run focused Riemann suite**

Run: `pytest -q tests/science/test_riemann_*.py`

Expected: PASS.

- [ ] **Step 2: Run science regression suite**

Run: `pytest -q tests/science`

Expected: PASS. Any unrelated pre-existing failure must be documented by exact test name and error summary.

- [ ] **Step 3: Run OMEGA adversarial and router regressions**

Run:

```bash
pytest -q tests/test_omega_adversarial.py tests/test_router.py tests/test_omega_orchestrator.py
python tools/adversarial_gate.py
```

Expected: PASS.

- [ ] **Step 4: Run full test suite if feasible**

Run: `pytest -q`

Expected: PASS or documented pre-existing/environmental failures.

- [ ] **Step 5: Inspect diff for governance weakening**

Run:

```bash
git diff --check
git diff --stat HEAD~10..HEAD
git status --short
```

Confirm:

- no secrets;
- no unrelated rollback;
- no weakened truth-gate wording;
- untracked `tools/offline_sara_public_plugin_validation.py` remains untouched unless the user separately asks to handle it.

- [ ] **Step 6: Final review summary**

Prepare a concise summary with:

- implemented modules;
- proof-status boundaries;
- adversarial gate results;
- remaining mathematical bottleneck: unconditional bound for `J_N = o(log^2 N)`.

Commit any final documentation-only measurement update:

```bash
git add BUILD_VERIFICATION.md
git commit -m "docs: record Riemann engine verification results"
```

only if `BUILD_VERIFICATION.md` changed after Task 9.

## Plan Self-Review

- Spec coverage: the plan covers proof-status models, arithmetic/Selberg coefficients, Baez-Duarte route encoding, Vasyunin/Gram computations, Mellin spectral records, proof gate, SARA provider/router integration, registry data, documentation, GitHub adversarial validation, and regression verification.
- Placeholder scan: the plan contains no unfinished-marker placeholders. Lightweight V3.4.0 scan scope is explicit and testable.
- Type consistency: all runtime result objects use `RiemannResult` and `RiemannProofStatus`; provider integration returns existing `ScienceAnalysis`; truth-gate integration uses deterministic dictionaries matching existing `evaluate_text_claim` behavior.
- Review focus coverage: finite extrapolation, circular assumptions, proof-status promotion, numerical stability, and router scope are each assigned to tests.
