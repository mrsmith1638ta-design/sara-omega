import math

from app.science.riemann.baez_duarte import tail_residual_sawtooth
from app.science.riemann.tail_attack import (
    certified_tail_interval,
    direct_period_mean_square,
    period_mean_square,
    pointwise_tail_residual_bound,
    residual_period,
    tail_attack_snapshot,
)


def test_tail_residual_is_periodic_for_fixed_n():
    for n in (4, 6, 8):
        period = residual_period(n)
        for y in (float(n), float(n) + 0.25, float(n) + 3.75, 2.5 * n):
            left = tail_residual_sawtooth(n, y)
            right = tail_residual_sawtooth(n, y + period)
            assert math.isclose(left, right, rel_tol=1e-11, abs_tol=1e-11)


def test_period_mean_square_formula_matches_direct_validation():
    for n in (3, 4, 5, 6, 8):
        formula = period_mean_square(n)
        direct = direct_period_mean_square(n)
        assert math.isclose(formula, direct, rel_tol=2e-10, abs_tol=2e-10)


def test_pointwise_bound_dominates_sampled_tail_residual():
    for n in (4, 8, 12):
        bound = pointwise_tail_residual_bound(n)
        period = residual_period(n)
        for j in range(80):
            y = n + (j + 0.37) * max(1.0, period / 40.0)
            assert abs(tail_residual_sawtooth(n, y)) <= bound + 1e-10


def test_certified_tail_interval_is_ordered_and_finite_n_only():
    cert = certified_tail_interval(8, 128)
    assert cert.certified_lower_bound >= 0.0
    assert cert.certified_upper_bound >= cert.certified_lower_bound
    assert cert.remainder_upper_bound > 0.0
    assert cert.proof_status == "NUMERICAL_EVIDENCE"
    assert cert.asymptotic_certified is False


def test_larger_cutoff_reduces_crude_remainder_bound():
    a = certified_tail_interval(8, 64)
    b = certified_tail_interval(8, 256)
    assert b.remainder_upper_bound < a.remainder_upper_bound


def test_tail_attack_snapshot_preserves_proof_boundary():
    snapshot = tail_attack_snapshot(8, 128)
    assert snapshot["phase"] == "TAIL_ATTACK_I"
    assert snapshot["asymptotic_certified"] is False
    assert snapshot["certificate"]["asymptotic_certified"] is False
    assert snapshot["proof_status"] == "NUMERICAL_EVIDENCE"
    assert "fixed-N certified enclosure" in snapshot["limitations"][1]
