from app.science.riemann.adversarial_gate import RHAdversarialGate
from app.science.riemann.models import RHProofStatus
from app.science.riemann.tail_attack_iv import BLOCKED, CONJECTURAL, FINITE_CERTIFIED
from app.science.riemann.tail_attack_v import (
    discrepancy_growth_search,
    mean_obstruction_audit,
    tail_attack_v_snapshot,
)


def test_mean_obstruction_audit_marks_near_sqrt_target_as_rh_sensitive():
    audit = mean_obstruction_audit()
    assert audit["phase"] == "TAIL_ATTACK_V"
    assert audit["target"] == "A_N=o(sqrt(N) log N)"
    assert audit["status"] == BLOCKED
    assert audit["rh_equivalence_risk"] == "HIGH"
    assert "1/(s^2 zeta(s))" in audit["zero_sensitive_transform"]["transform"]
    assert audit["promotion_rule"] == "proof_grade_dependency_required"


def test_discrepancy_growth_search_keeps_finite_diagnostics_conjectural():
    search = discrepancy_growth_search((4, 6, 8))
    assert search["phase"] == "TAIL_ATTACK_V"
    assert search["uniform_target"] == "D_N/N^2=o(log^2 N)"
    assert search["uniform_status"] == CONJECTURAL
    assert search["finite_status"] == FINITE_CERTIFIED
    assert all(row["status"] == FINITE_CERTIFIED for row in search["finite_rows"])
    assert "finite subperiod patterns do not prove a uniform asymptotic" in search["red_team_boundary"]


def test_tail_attack_v_snapshot_preserves_two_live_doors():
    snapshot = tail_attack_v_snapshot()
    assert snapshot["phase"] == "TAIL_ATTACK_V"
    assert snapshot["program"] == "Mean Obstruction Audit + Discrepancy Growth Search"
    assert snapshot["uniform_tail_status"] == BLOCKED
    assert snapshot["dependencies"]["covariance"]["status"] == "proved"
    assert snapshot["dependencies"]["mean"]["status"] == BLOCKED
    assert snapshot["dependencies"]["discrepancy"]["status"] == CONJECTURAL
    assert snapshot["proof_boundary"]["rh_proved"] is False


def test_tail_attack_v_gate_blocks_mean_shortcut_and_combined_claim():
    gate = RHAdversarialGate()
    result = gate.evaluate_tail_attack_v_claim(
        "The near-square-root mean bound follows from the zeta zero structure, therefore RH follows.",
        proof_status=RHProofStatus.CONJECTURAL_LEMMA,
        mean_obstruction_resolved=False,
        discrepancy_growth_proved=False,
        combined_tail_claim=True,
        uses_zero_structure_shortcut=True,
    )
    assert result.allowed is False
    assert any("mean obstruction" in reason for reason in result.reasons)
    assert any("zero-structure" in reason for reason in result.reasons)
    assert any("combined Tail Attack V promotion" in reason for reason in result.reasons)
