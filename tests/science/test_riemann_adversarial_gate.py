from app.science.riemann.adversarial_gate import RHAdversarialGate
from app.science.riemann.models import RHProofStatus
from app.science.router import ScienceRouter


def test_numerical_evidence_cannot_be_promoted_to_rh_proof():
    result = RHAdversarialGate().evaluate(
        claim="RH proved",
        proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
        finite_n_only=True,
    )
    assert result.allowed is False
    assert result.status == "BLOCK"


def test_conjectural_lemma_cannot_be_promoted_to_rh_proof():
    result = RHAdversarialGate().evaluate(
        claim="Therefore the Riemann Hypothesis is true",
        proof_status=RHProofStatus.CONJECTURAL_LEMMA,
    )
    assert result.allowed is False


def test_formal_status_requires_certificate_and_infinite_limit():
    gate = RHAdversarialGate()
    blocked = gate.certify_status(RHProofStatus.FORMAL_PROOF_CERTIFIED)
    assert blocked.allowed is False
    allowed = gate.certify_status(
        RHProofStatus.FORMAL_PROOF_CERTIFIED,
        formal_certificate="formal-proof-artifact:example",
        infinite_limit_proved=True,
    )
    assert allowed.allowed is True




def test_finite_tail_certificate_cannot_promote_to_asymptotic_little_o():
    result = RHAdversarialGate().evaluate(
        claim="The tail satisfies T_N=o(log^2 N).",
        proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
        finite_n_only=True,
        claims_asymptotic_limit=True,
        uniform_asymptotic_proved=False,
    )
    assert result.allowed is False
    assert any("finite-N tail certification" in reason for reason in result.reasons)
    assert any("uniform N-to-infinity" in reason for reason in result.reasons)



def test_tail_attack_ii_blocks_covariance_only_uniform_tail_claim():
    result = RHAdversarialGate().evaluate_tail_attack_ii_uniform_claim(
        "Covariance is O(N), therefore the tail is o(log^2 N).",
        proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
        covariance_uniform_bound_proved=True,
        mean_component_uniform_bound_proved=False,
        cumulative_energy_discrepancy_proved=False,
        period_to_tail_transfer_proved=False,
    )
    assert result.allowed is False
    assert any("mean-component" in reason for reason in result.reasons)
    assert any("cumulative-energy discrepancy" in reason for reason in result.reasons)
    assert any("covariance control alone" in reason for reason in result.reasons)


def test_tail_attack_ii_blocks_unproved_mobius_randomness():
    result = RHAdversarialGate().evaluate_tail_attack_ii_uniform_claim(
        "Use square-root Mobius cancellation to obtain the uniform tail bound.",
        proof_status=RHProofStatus.CONJECTURAL_LEMMA,
        covariance_uniform_bound_proved=True,
        mean_component_uniform_bound_proved=True,
        cumulative_energy_discrepancy_proved=True,
        period_to_tail_transfer_proved=True,
        assumes_mobius_randomness=True,
    )
    assert result.allowed is False
    assert any("Mobius randomness" in reason for reason in result.reasons)



def test_tail_attack_iii_blocks_finite_period_to_tail_shortcut():
    result = RHAdversarialGate().evaluate_tail_attack_iii_claim(
        "Finite period therefore period average equals tail.",
        proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
        covariance_bound_proved=True,
        mean_component_bound_proved=False,
        discrepancy_bound_proved=False,
        weighted_transfer_proved=True,
        finite_period_only=True,
    )
    assert result.allowed is False
    assert any("finite-period average" in reason for reason in result.reasons)
    assert any("mean-component target" in reason for reason in result.reasons)
    assert any("discrepancy target" in reason for reason in result.reasons)


def test_tail_attack_iii_blocks_hidden_pnt_strength_and_mobius_randomness():
    result = RHAdversarialGate().evaluate_tail_attack_iii_claim(
        "Use square-root cancellation in Mobius to finish the mean component.",
        proof_status=RHProofStatus.CONJECTURAL_LEMMA,
        covariance_bound_proved=True,
        mean_component_bound_proved=True,
        discrepancy_bound_proved=True,
        weighted_transfer_proved=True,
        assumes_mobius_randomness=True,
        assumes_unproved_pnt_strength=True,
    )
    assert result.allowed is False
    assert any("Mobius randomness" in reason for reason in result.reasons)
    assert any("PNT-strength" in reason for reason in result.reasons)



def test_tail_attack_iv_blocks_unsourced_mean_and_finite_discrepancy_promotion():
    result = RHAdversarialGate().evaluate_tail_attack_iv_claim(
        "Use the period data to finish the tail theorem.",
        proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
        mean_bound_sourced=False,
        mean_target_proved=False,
        covariance_target_proved=True,
        discrepancy_target_proved=False,
        combined_tail_claim=True,
        finite_period_or_subperiod_only=True,
    )
    assert result.allowed is False
    assert any("explicit source" in reason for reason in result.reasons)
    assert any("mean dependency" in reason for reason in result.reasons)
    assert any("finite period/subperiod" in reason for reason in result.reasons)
    assert any("combined weighted-tail promotion" in reason for reason in result.reasons)


def test_tail_attack_iv_blocks_hidden_rh_and_mobius_randomness():
    result = RHAdversarialGate().evaluate_tail_attack_iv_claim(
        "Assuming RH and square-root cancellation, the dashboard is complete.",
        proof_status=RHProofStatus.CONJECTURAL_LEMMA,
        mean_bound_sourced=True,
        mean_target_proved=True,
        covariance_target_proved=True,
        discrepancy_target_proved=True,
        combined_tail_claim=True,
        assumes_rh=True,
        assumes_mobius_randomness=True,
    )
    assert result.allowed is False
    assert any("cannot assume RH" in reason for reason in result.reasons)
    assert any("Mobius randomness" in reason for reason in result.reasons)


def test_tail_attack_v_blocks_mean_obstruction_shortcut():
    result = RHAdversarialGate().evaluate_tail_attack_v_claim(
        "The near-square-root follows from zeta zero structure, so RH follows.",
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


def test_rh_router_activation():
    routed = ScienceRouter().route_text(
        "Analyze the Riemann Hypothesis with Nyman Beurling, Baez-Duarte, Gram matrix and J_N."
    )
    assert "riemann_hypothesis" in routed
    covariance_routed = ScienceRouter().route_text(
        "Run Tail Attack II on the gcd covariance and Jordan totient layers."
    )
    assert "riemann_hypothesis" in covariance_routed
    tail_iii_routed = ScienceRouter().route_text(
        "Run Tail Attack III on the mean component and weighted tail transfer discrepancy."
    )
    assert "riemann_hypothesis" in tail_iii_routed
    tail_iv_routed = ScienceRouter().route_text(
        "Run Tail Attack IV mean and discrepancy growth dashboard."
    )
    assert "riemann_hypothesis" in tail_iv_routed
    tail_v_routed = ScienceRouter().route_text(
        "Run Tail Attack V mean obstruction audit and discrepancy growth search."
    )
    assert "riemann_hypothesis" in tail_v_routed
