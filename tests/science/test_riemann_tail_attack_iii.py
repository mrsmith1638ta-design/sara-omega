import math

from app.science.riemann.tail_attack import certified_tail_interval, period_mean_square, residual_period
from app.science.riemann.tail_attack_iii import (
    centered_residual_identity,
    cumulative_energy_discrepancy,
    discrepancy_periodicity_check,
    fixed_n_discrepancy_supremum,
    mean_component,
    mean_component_mertens_form,
    period_energy_mean,
    periodic_transfer_interval,
    tail_attack_iii_snapshot,
)


def test_centered_residual_decomposition_is_exact():
    for n in (4, 6, 8, 10):
        for y in (float(n), float(n) + 0.25, float(n) + 2.75, 3.5 * n):
            result = centered_residual_identity(n, y)
            assert result["absolute_error"] < 2e-11


def test_mean_component_matches_mertens_partial_summation():
    for n in (4, 8, 16, 32, 64):
        assert math.isclose(
            mean_component(n),
            mean_component_mertens_form(n),
            rel_tol=2e-12,
            abs_tol=2e-12,
        )


def test_period_energy_splits_into_mean_plus_covariance():
    for n in (4, 6, 8, 10):
        assert math.isclose(
            period_energy_mean(n),
            period_mean_square(n),
            rel_tol=2e-10,
            abs_tol=2e-10,
        )


def test_energy_discrepancy_is_periodic_for_fixed_n():
    for n in (4, 6, 8):
        period = residual_period(n)
        for y in (float(n), float(n) + 0.5, float(n) + 3.25):
            result = discrepancy_periodicity_check(n, y)
            assert result["absolute_error"] < 2e-7
        assert abs(cumulative_energy_discrepancy(n, n + period)) < 2e-7


def test_fixed_n_discrepancy_supremum_closes_period():
    result = fixed_n_discrepancy_supremum(8)
    assert result["period"] == residual_period(8)
    assert result["supremum"] >= 0.0
    assert result["period_endpoint_error"] < 2e-7


def test_periodic_transfer_certificate_overlaps_tail_attack_i_certificate():
    periodic = periodic_transfer_interval(8)
    tail_i = certified_tail_interval(8, 256)
    assert periodic.transfer_lower_bound <= periodic.transfer_upper_bound
    assert periodic.transfer_lower_bound <= tail_i.certified_upper_bound
    assert tail_i.certified_lower_bound <= periodic.transfer_upper_bound
    assert periodic.uniform_tail_certified is False


def test_tail_attack_iii_snapshot_preserves_uniform_proof_boundary():
    snapshot = tail_attack_iii_snapshot(8)
    assert snapshot["phase"] == "TAIL_ATTACK_III"
    assert snapshot["uniform_tail_certified"] is False
    assert snapshot["mean_component"]["uniform_target_certified"] is False
    assert snapshot["transfer"]["uniform_discrepancy_target_certified"] is False
    assert snapshot["tail_i_cross_check"]["intervals_overlap"] is True
    assert any("A_N=o(sqrt(N) log N)" in gap for gap in snapshot["remaining_uniform_gaps"])
