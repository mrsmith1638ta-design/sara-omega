import math

from app.science.riemann.baez_duarte import (
    RiemannResearchEngine,
    finite_range_psi_identity,
    mobius_sieve,
    residual_identity,
    theta_n,
    theta_n_mobius_form,
    truncated_j_n,
)


def test_mobius_sieve_reference_values():
    mu = mobius_sieve(10)
    assert mu[1:11] == [1, -1, -1, 0, -1, 1, -1, 0, 0, 1]


def test_theta_forms_are_identical():
    for n in (4, 8, 16, 32):
        assert math.isclose(theta_n(n), theta_n_mobius_form(n), rel_tol=1e-12, abs_tol=1e-12)


def test_exact_pointwise_residual_identity():
    for n in (4, 8, 16):
        for y in (1.0, 1.5, 2.0, 3.25, float(n), float(n) + 2.5):
            result = residual_identity(n, y)
            assert result["absolute_error"] < 1e-10


def test_psi_n_equals_chebyshev_psi_on_finite_range():
    n = 24
    for y in range(1, n + 1):
        result = finite_range_psi_identity(n, float(y))
        assert result["absolute_error"] < 1e-10


def test_truncated_j_is_nonnegative_and_finite():
    value = truncated_j_n(8, 32)
    assert math.isfinite(value)
    assert value >= 0.0


def test_engine_never_self_certifies_rh():
    analysis = RiemannResearchEngine().analyze_text("Investigate the Riemann Hypothesis.")
    assert analysis.metadata["rh_status"] == "UNSOLVED"
    assert analysis.metadata["formal_proof_certified"] is False
    assert analysis.metadata["proof_promotion_gate"]["false_promotion_allowed"] is False
    statuses = {
        item.result.get("proof_status")
        for item in analysis.calculations
        if isinstance(item.result, dict) and "proof_status" in item.result
    }
    assert "FORMAL_PROOF_CERTIFIED" not in statuses
