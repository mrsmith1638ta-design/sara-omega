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


def test_rh_router_activation():
    routed = ScienceRouter().route_text(
        "Analyze the Riemann Hypothesis with Nyman Beurling, Baez-Duarte, Gram matrix and J_N."
    )
    assert "riemann_hypothesis" in routed
