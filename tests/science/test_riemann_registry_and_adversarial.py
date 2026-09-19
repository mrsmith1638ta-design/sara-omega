from app.science.registry import ScienceRegistry


def test_riemann_registry_records_load():
    registry = ScienceRegistry.default()
    assert registry.get_equation("riemann.baez_duarte_distance")["domain"] == "riemann_hypothesis"
    assert registry.get_equation("riemann.J_N_bottleneck")["provenance_class"] == "MODERN_ENGINEERING_DERIVATION"
    assert registry.get_source("riemann.local.v340_spec")["evidence_status"] == "UNVERIFIED"


def test_provider_consensus_cannot_certify_RH():
    from app.science.riemann.models import RiemannProofStatus, RiemannResult
    from app.science.riemann.proof_gate import RiemannProofGate

    result = RiemannResult(
        statement="Three providers agree RH is solved.",
        status=RiemannProofStatus.CANDIDATE_LEMMA,
        evidence=["provider:a", "provider:b", "provider:c"],
    )
    decision = RiemannProofGate().evaluate("Providers agree RH is proved.", result)
    assert decision["allowed_as_proof"] is False


def test_quantum_interpretation_cannot_certify_RH():
    from app.science.riemann.proof_gate import RiemannProofGate

    decision = RiemannProofGate().evaluate("The dilation Hamiltonian spectrum proves RH.")
    assert decision["allowed_as_proof"] is False

