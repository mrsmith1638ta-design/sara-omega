import math

from app.science.riemann.adversarial_gate import RHAdversarialGate
from app.science.riemann.models import RHProofStatus
from app.science.riemann.rh_route_pivot import (
    constrained_gram_solution,
    pivot_b_snapshot,
    rh_route_pivot_snapshot,
)
from app.science.riemann.vasyunin import d_squared


def test_pivot_b_enforces_mean_zero_constraints_and_reports_penalty():
    result = constrained_gram_solution(6, enforce_sum_over_n_zero=True)
    assert math.isclose(result["constraints"]["sum_c"], 2.0, rel_tol=1e-10, abs_tol=1e-10)
    assert math.isclose(result["constraints"]["sum_c_over_n"], 0.0, rel_tol=1e-10, abs_tol=1e-10)
    assert result["constrained_distance_squared"] >= d_squared(6) - 1e-10
    assert math.isclose(
        result["penalty"],
        result["constrained_distance_squared"] - result["unconstrained_distance_squared"],
        rel_tol=1e-10,
        abs_tol=1e-10,
    )
    assert result["penalty"] >= -1e-10
    assert result["proof_status"] == "NUMERICAL_EVIDENCE"


def test_pivot_b_can_use_sum_constraint_alone():
    result = constrained_gram_solution(6, enforce_sum_over_n_zero=False)
    assert math.isclose(result["constraints"]["sum_c"], 2.0, rel_tol=1e-10, abs_tol=1e-10)
    assert "sum_c_over_n" not in result["constraints"]
    assert result["constraint_labels"] == ["sum_c_equals_2"]


def test_rh_route_pivot_snapshot_stops_tail_sequence():
    snapshot = rh_route_pivot_snapshot(6)
    assert snapshot["phase"] == "RH_ROUTE_PIVOT"
    assert snapshot["not_tail_attack_vi"] is True
    assert snapshot["pivot_b"]["central_question"] == "Does the constrained approximation penalty tend to zero?"
    assert snapshot["pivot_b"]["uniform_status"] == "conjectural"
    assert snapshot["pivot_a"]["status"] == "research_target"
    assert snapshot["rh_proved"] is False


def test_pivot_b_snapshot_tracks_two_constraint_variants():
    snapshot = pivot_b_snapshot(6)
    assert snapshot["phase"] == "RH_ROUTE_PIVOT_B"
    assert snapshot["primary_experiment"] == "mean-zero constrained coefficients"
    assert snapshot["sum_constraint_only"]["constraint_labels"] == ["sum_c_equals_2"]
    assert snapshot["sum_and_reciprocal_constraint"]["constraint_labels"] == [
        "sum_c_equals_2",
        "sum_c_over_n_equals_0",
    ]


def test_route_pivot_gate_blocks_finite_penalty_promotion():
    result = RHAdversarialGate().evaluate_route_pivot_claim(
        "The constrained penalty is small for tested N, therefore RH follows.",
        proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
        constrained_penalty_uniform_proved=False,
        signed_transfer_uniform_proved=False,
        combined_route_claim=True,
        finite_n_only=True,
    )
    assert result.allowed is False
    assert any("finite constrained-penalty data" in reason for reason in result.reasons)
    assert any("combined RH Route Pivot" in reason for reason in result.reasons)
