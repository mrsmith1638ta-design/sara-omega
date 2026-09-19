import math

from app.science.riemann.tail_attack_iv import (
    BLOCKED,
    CONJECTURAL,
    FINITE_CERTIFIED,
    PROVED,
    combined_tail_dashboard,
    deterministic_period_discrepancy_bound,
    discrepancy_growth_snapshot,
    known_mertens_bound_catalog,
    mean_growth_snapshot,
    subperiod_discrepancy_profile,
    tail_attack_iv_snapshot,
    weighted_mobius_mellin_statement,
)


def test_mertens_catalog_separates_known_bounds_from_tail_iv_target():
    catalog = known_mertens_bound_catalog()
    by_id = {item["bound_id"]: item for item in catalog}
    assert by_id["prime_number_theorem"]["status"] == PROVED
    assert by_id["korobov_vinogradov_zero_free_region"]["status"] == PROVED
    assert by_id["prime_number_theorem"]["reaches_tail_iv_mean_target"] is False
    assert by_id["korobov_vinogradov_zero_free_region"]["reaches_tail_iv_mean_target"] is False
    assert by_id["tail_iv_required_mean_rate"]["status"] == CONJECTURAL
    assert by_id["tail_iv_required_mean_rate"]["rh_sensitive"] is True


def test_weighted_mobius_mellin_record_exposes_zeta_denominator():
    record = weighted_mobius_mellin_statement()
    assert record["status"] == PROVED
    assert "1/(s^2 zeta(s))" in record["transform"]


def test_deterministic_period_discrepancy_bound_dominates_fixed_snapshot():
    bound = deterministic_period_discrepancy_bound(8)
    rows = discrepancy_growth_snapshot((8,))
    assert len(rows) == 1
    assert rows[0]["D_N"] <= bound + 1e-8


def test_subperiod_profile_is_finite_certified_only():
    rows = subperiod_discrepancy_profile(8, block_sizes=(1, 2, 4, 8, 16))
    assert rows
    assert all(row["status"] == FINITE_CERTIFIED for row in rows)
    assert all(row["max_absolute_block_discrepancy"] >= 0.0 for row in rows)


def test_mean_growth_snapshot_reports_target_ratio_without_promotion():
    rows = mean_growth_snapshot((8, 16, 32))
    assert [row["n"] for row in rows] == [8, 16, 32]
    assert all(math.isfinite(row["target_ratio"]) for row in rows)


def test_combined_tail_dashboard_has_component_statuses():
    dashboard = combined_tail_dashboard(8)
    assert dashboard["inequality"] == "T_N <= A_N^2/N + C_N/N + D_N/N^2"
    assert dashboard["terms"]["mean"]["uniform_status"] == BLOCKED
    assert dashboard["terms"]["covariance"]["uniform_status"] == PROVED
    assert dashboard["terms"]["discrepancy"]["uniform_status"] == CONJECTURAL
    assert dashboard["finite_upper_status"] == FINITE_CERTIFIED
    assert dashboard["uniform_tail_status"] == BLOCKED
    expected = sum(term["value"] for term in dashboard["terms"].values())
    assert math.isclose(dashboard["finite_upper_bound"], expected, rel_tol=1e-12, abs_tol=1e-12)


def test_tail_attack_iv_snapshot_preserves_dependency_graph_boundary():
    snapshot = tail_attack_iv_snapshot(8)
    assert snapshot["phase"] == "TAIL_ATTACK_IV"
    assert snapshot["program"] == "Mean + Discrepancy Growth Program"
    assert snapshot["uniform_tail_certified"] is False
    assert snapshot["dashboard"]["dependency_graph"]["covariance_uniform_bound"]["status"] == PROVED
    assert snapshot["dashboard"]["dependency_graph"]["mean_uniform_target"]["status"] == BLOCKED
    assert snapshot["dashboard"]["dependency_graph"]["discrepancy_uniform_target"]["status"] == CONJECTURAL
