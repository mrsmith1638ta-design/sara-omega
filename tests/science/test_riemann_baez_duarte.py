import math

from app.science.riemann.baez_duarte import (
    RiemannResearchEngine,
    equation_registry,
    finite_range_j_n,
    finite_range_psi_identity,
    j_split_snapshot,
    mobius_sieve,
    psi_n,
    residual_identity,
    tail_residual_sawtooth,
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




def test_tail_sawtooth_identity_matches_theta_minus_psi_n():
    for n in (4, 8, 16):
        theta = theta_n(n)
        for y in (1.0, 2.5, float(n), float(n) + 7.25, 3.0 * n + 0.5):
            direct = theta * y - psi_n(y, n)
            saw = tail_residual_sawtooth(n, y)
            assert math.isclose(direct, saw, rel_tol=1e-11, abs_tol=1e-11)


def test_j_split_snapshot_is_exact_through_cutoff():
    data = j_split_snapshot(8, 32)
    assert data["finite_range_1_to_N"] == finite_range_j_n(8)
    assert math.isclose(
        data["finite_range_1_to_N"] + data["tail_window_N_to_cutoff"],
        data["through_cutoff"],
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert data["tail_beyond_cutoff_uncomputed"] is True


def test_conversation_equations_are_registered():
    ids = {item.equation_id for item in equation_registry()}
    required = {
        "rh.constructive_residual",
        "rh.mobius_divisor_identity",
        "rh.log_mobius_divisor_identity",
        "rh.finite_range_residual",
        "rh.l2_exact",
        "rh.j_n",
        "rh.j_split",
        "rh.tail_sawtooth",
        "rh.tail_periodicity",
        "rh.tail_period_mean_square",
        "rh.tail_covariance_jordan",
        "rh.tail_covariance_squarefree_layers",
        "rh.tail_covariance_linear_bound",
        "rh.tail_energy_transfer",
        "rh.tail_attack_ii_target",
        "rh.tail_centered_decomposition",
        "rh.tail_mean_mertens",
        "rh.tail_period_energy_components",
        "rh.tail_discrepancy",
        "rh.tail_transfer_exact",
        "rh.tail_transfer_error",
        "rh.tail_attack_iii_target",
        "rh.tail_weighted_mobius_mellin",
        "rh.tail_discrepancy_period_bound",
        "rh.tail_iv_dashboard_bound",
        "rh.tail_attack_iv_target",
        "rh.stronger_finite_target",
        "rh.sufficient_target",
        "rh.sufficient_implication_chain",
    }
    assert required.issubset(ids)


def test_engine_never_self_certifies_rh():
    analysis = RiemannResearchEngine().analyze_text("Investigate the Riemann Hypothesis.")
    assert analysis.metadata["rh_status"] == "UNSOLVED"
    assert analysis.metadata["formal_proof_certified"] is False
    assert analysis.metadata["proof_promotion_gate"]["false_promotion_allowed"] is False
    assert analysis.metadata["tail_attack_ii"]["enabled"] is True
    assert analysis.metadata["tail_attack_ii"]["uniform_covariance_linear_bound_proved"] is True
    assert analysis.metadata["tail_attack_ii"]["uniform_tail_certified"] is False
    assert analysis.metadata["tail_attack_iii"]["enabled"] is True
    assert analysis.metadata["tail_attack_iii"]["exact_weighted_transfer_identity"] is True
    assert analysis.metadata["tail_attack_iii"]["uniform_tail_certified"] is False
    assert analysis.metadata["tail_attack_iv"]["enabled"] is True
    assert analysis.metadata["tail_attack_iv"]["combined_tail_dashboard"] is True
    assert analysis.metadata["tail_attack_iv"]["covariance_uniform_status"] == "proved"
    assert analysis.metadata["tail_attack_iv"]["uniform_tail_status"] == "blocked"
    statuses = {
        item.result.get("proof_status")
        for item in analysis.calculations
        if isinstance(item.result, dict) and "proof_status" in item.result
    }
    assert "FORMAL_PROOF_CERTIFIED" not in statuses
