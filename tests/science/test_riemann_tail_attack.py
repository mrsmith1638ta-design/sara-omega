import math

from app.science.riemann.adversarial_gate import RHAdversarialGate
from app.science.riemann.baez_duarte import RiemannResearchEngine, equation_registry, tail_attack_snapshot
from app.science.riemann.models import RHProofStatus


def test_tail_attack_snapshot_tracks_finite_tail_window_and_sawtooth_samples():
    snapshot = tail_attack_snapshot(8, 32, sample_count=9)

    assert snapshot["phase"] == "Tail Attack I"
    assert snapshot["proof_status"] == RHProofStatus.NUMERICAL_EVIDENCE.value
    assert snapshot["N"] == 8
    assert snapshot["cutoff"] == 32
    assert snapshot["tail_window_N_to_cutoff"] >= 0.0
    assert snapshot["tail_beyond_cutoff_uncomputed"] is True
    assert len(snapshot["sawtooth_samples"]) == 9
    assert math.isfinite(snapshot["tail_window_rms"])


def test_tail_attack_equation_is_registered_as_research_not_proof():
    equations = {item.equation_id: item for item in equation_registry()}

    tail_attack = equations["rh.tail_attack_i"]
    assert tail_attack.proof_status == RHProofStatus.NUMERICAL_EVIDENCE
    assert "does not prove" in " ".join(tail_attack.notes).lower()


def test_tail_bound_red_team_rejects_hidden_RH_and_sqrt_cancellation():
    gate = RHAdversarialGate()

    hidden_rh = gate.evaluate_tail_bound_claim(
        "The tail is small because all zeta zeros lie on the critical line.",
        proof_status=RHProofStatus.CONJECTURAL_LEMMA,
    )
    assert hidden_rh.allowed is False
    assert any("rh" in reason.lower() or "zero" in reason.lower() for reason in hidden_rh.reasons)

    sqrt_cancellation = gate.evaluate_tail_bound_claim(
        "Assume square-root cancellation in the fractional-part sum, so the tail is o(log^2 N).",
        proof_status=RHProofStatus.CONJECTURAL_LEMMA,
    )
    assert sqrt_cancellation.allowed is False
    assert any("cancellation" in reason.lower() for reason in sqrt_cancellation.reasons)


def test_engine_exposes_tail_attack_i_metadata_without_certifying_RH():
    analysis = RiemannResearchEngine().analyze_text("Run Tail Attack I on the RH J_N tail.")

    assert analysis.metadata["tail_attack_i"]["phase"] == "Tail Attack I"
    assert analysis.metadata["formal_proof_certified"] is False
    assert analysis.metadata["tail_attack_i"]["proof_status"] == RHProofStatus.NUMERICAL_EVIDENCE.value
    assert any(item.equation_id == "rh.tail_attack_i_snapshot" for item in analysis.calculations)

