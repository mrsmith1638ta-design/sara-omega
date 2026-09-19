from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
        gate.evaluate(
            claim="The tail satisfies T_N=o(log^2 N).",
            proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
            finite_n_only=True,
            claims_asymptotic_limit=True,
            uniform_asymptotic_proved=False,
        ),
        gate.evaluate_tail_attack_ii_uniform_claim(
            "Covariance is O(N), therefore the tail is o(log^2 N).",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            covariance_uniform_bound_proved=True,
            mean_component_uniform_bound_proved=False,
            cumulative_energy_discrepancy_proved=False,
            period_to_tail_transfer_proved=False,
        ),
        gate.evaluate_tail_attack_iii_claim(
            "Finite period therefore period average equals tail.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            covariance_bound_proved=True,
            mean_component_bound_proved=False,
            discrepancy_bound_proved=False,
            weighted_transfer_proved=True,
            finite_period_only=True,
        ),
        gate.evaluate_tail_attack_iv_claim(
            "Use the finite subperiod dashboard to finish the weighted tail.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            mean_bound_sourced=False,
            mean_target_proved=False,
            covariance_target_proved=True,
            discrepancy_target_proved=False,
            combined_tail_claim=True,
            finite_period_or_subperiod_only=True,
        ),
        gate.evaluate_tail_attack_v_claim(
            "The near-square-root mean bound follows from zeta zero structure, so RH follows.",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
            mean_obstruction_resolved=False,
            discrepancy_growth_proved=False,
            combined_tail_claim=True,
            uses_zero_structure_shortcut=True,
        ),
        gate.evaluate_route_pivot_claim(
            "The constrained penalty is small for tested N, therefore RH follows.",
            proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
            constrained_penalty_uniform_proved=False,
            signed_transfer_uniform_proved=False,
            combined_route_claim=True,
            finite_n_only=True,
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
        "finite_tail_asymptotic_promotion_blocked": True,
        "tail_attack_ii_covariance_only_promotion_blocked": True,
        "tail_attack_iii_period_to_tail_shortcut_blocked": True,
        "tail_attack_iv_dependency_promotion_blocked": True,
        "tail_attack_v_mean_obstruction_promotion_blocked": True,
        "rh_route_pivot_finite_penalty_promotion_blocked": True,
        "formal_proof_certified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
