import math

from app.science.riemann.gcd_covariance import (
    COVARIANCE_LINEAR_CONSTANT,
    conditional_tail_transfer_bound,
    covariance_certificate,
    covariance_linear_upper_bound,
    gcd_covariance_coprime_layers,
    gcd_covariance_direct,
    gcd_covariance_jordan,
    jordan_totient_2_sieve,
    max_layer_identity_error,
    tail_attack_ii_snapshot,
)


def test_jordan_totient_2_reference_values():
    values = jordan_totient_2_sieve(6)
    assert values[1:7] == [1, 3, 8, 12, 24, 24]


def test_gcd_covariance_decompositions_agree():
    for n in (4, 8, 12, 16):
        direct = gcd_covariance_direct(n)
        jordan = gcd_covariance_jordan(n)
        coprime = gcd_covariance_coprime_layers(n)
        assert math.isclose(direct, jordan, rel_tol=2e-11, abs_tol=2e-11)
        assert math.isclose(jordan, coprime, rel_tol=2e-11, abs_tol=2e-11)
        assert max_layer_identity_error(n) < 2e-12


def test_unconditional_linear_covariance_bound_holds_on_regression_grid():
    assert COVARIANCE_LINEAR_CONSTANT < 9.14
    for n in (4, 8, 16, 32, 64, 128):
        covariance = gcd_covariance_jordan(n)
        assert covariance >= 0.0
        assert covariance <= covariance_linear_upper_bound(n) + 1e-10


def test_covariance_certificate_preserves_tail_boundary():
    cert = covariance_certificate(32)
    assert cert.jordan_covariance >= 0.0
    assert cert.linear_upper_bound >= cert.jordan_covariance
    assert cert.jordan_direct_absolute_error is not None
    assert cert.jordan_direct_absolute_error < 2e-10
    assert cert.jordan_coprime_absolute_error < 2e-10
    assert cert.uniform_tail_certified is False


def test_conditional_tail_transfer_evaluates_only_the_rhs():
    value = conditional_tail_transfer_bound(
        100,
        mean_square=25.0,
        discrepancy_bound=400.0,
    )
    assert math.isclose(value, 0.29, rel_tol=1e-15, abs_tol=1e-15)


def test_tail_attack_ii_snapshot_identifies_real_remaining_gap():
    snapshot = tail_attack_ii_snapshot(32)
    assert snapshot["phase"] == "TAIL_ATTACK_II"
    assert snapshot["cross_layer_cancellation"] is False
    assert snapshot["uniform_tail_certified"] is False
    assert "C_N <= K*N" in snapshot["uniform_covariance_bound"]
    assert any("period-to-tail" in item for item in snapshot["remaining_uniform_gaps"])
    assert all(row["contribution"] >= 0.0 for row in snapshot["top_layers"])
