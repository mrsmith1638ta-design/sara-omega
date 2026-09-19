from __future__ import annotations

import json

from app.science.riemann.adversarial_gate import RHAdversarialGate
from app.science.riemann.baez_duarte import (
    RiemannResearchEngine,
    finite_range_psi_identity,
    residual_identity,
)
from app.science.riemann.models import RHProofStatus
from app.science.riemann.vasyunin import schur_extension


def main() -> int:
    gate = RHAdversarialGate()

    false_claims = [
        gate.evaluate(
            claim="RH proved",
            proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
            finite_n_only=True,
        ),
        gate.evaluate(
            claim="Therefore the Riemann Hypothesis is true",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
        ),
        gate.evaluate(
            claim="Riemann Hypothesis proved",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
        ),
        gate.evaluate(
            claim="RH proved",
            proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
            spectral_or_quantum_only=True,
        ),
    ]
    assert all(not item.allowed for item in false_claims)

    for n in (4, 8, 16):
        for y in (1.0, 1.5, float(n), float(n) + 2.25):
            assert residual_identity(n, y)["absolute_error"] < 1e-10
        for y in range(1, n + 1):
            assert finite_range_psi_identity(n, float(y))["absolute_error"] < 1e-10

    for n in (2, 3, 4, 5):
        schur = schur_extension(n)
        assert schur["s_n"] > 0.0
        assert schur["absolute_error"] < 2e-9

    analysis = RiemannResearchEngine().analyze_text("Riemann Hypothesis proof research")
    assert analysis.metadata["rh_status"] == "UNSOLVED"
    assert analysis.metadata["formal_proof_certified"] is False

    print(json.dumps({
        "status": "PASS",
        "engine": "sara-riemann-research",
        "false_proof_promotion_blocked": True,
        "finite_n_limit_promotion_blocked": True,
        "rh_assumption_circularity_gate": True,
        "spectral_quantum_only_certification_blocked": True,
        "symbolic_identities_checked": True,
        "schur_recursion_checked": True,
        "formal_proof_certified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
