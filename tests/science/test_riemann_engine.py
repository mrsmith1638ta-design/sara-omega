import math

import pytest

from app.models import Assignment, Problem
from app.router import OmegaRouter
from app.science.provider import ScienceSpecialist
from app.science.truth_gate import HighLevelTruthGate


def test_proof_status_requires_certificate_for_formal_proof():
    from app.science.riemann.models import RiemannProofStatus, RiemannResult

    with pytest.raises(ValueError, match="certificate"):
        RiemannResult(statement="RH proof", status=RiemannProofStatus.FORMAL_PROOF_CERTIFIED)


def test_only_formal_certificate_supports_proof_language():
    from app.science.riemann.models import (
        RiemannProofStatus,
        RiemannResult,
        classify_user_facing_strength,
    )

    numerical = RiemannResult(
        statement="d_N decreased for tested N",
        status=RiemannProofStatus.NUMERICAL_EVIDENCE,
        evidence=["N=20 finite computation"],
    )
    certified = RiemannResult(
        statement="A certified theorem statement",
        status=RiemannProofStatus.FORMAL_PROOF_CERTIFIED,
        evidence=["lean:theorem_id"],
        certificate_id="lean:theorem_id",
    )

    assert classify_user_facing_strength(numerical) == "observed for tested finite cases"
    assert classify_user_facing_strength(certified) == "formal proof certified"


def test_mobius_and_selberg_small_values():
    from app.science.riemann.mobius import mobius_values
    from app.science.riemann.selberg import finite_psi_N, selberg_coefficients

    assert mobius_values(10) == [1, -1, -1, 0, -1, 1, -1, 0, 0, 1]
    coeffs = selberg_coefficients(8)
    assert coeffs[0] == -1.0
    assert math.isclose(coeffs[7], 0.0, abs_tol=1e-12)
    assert math.isclose(finite_psi_N(10, 1), 0.0, abs_tol=1e-12)
    assert math.isclose(finite_psi_N(10, 2), math.log(2), rel_tol=1e-12)


def test_baez_duarte_route_is_candidate_not_proof():
    from app.science.riemann.baez_duarte import error_norm_identity_record, riemann_sufficient_target, split_J_target
    from app.science.riemann.models import RiemannProofStatus

    route = riemann_sufficient_target()
    assert route.status == RiemannProofStatus.CANDIDATE_LEMMA
    assert "J_N = o(log^2 N)" in route.statement
    assert "Baez-Duarte" in " ".join(route.evidence)

    identity = error_norm_identity_record(20)
    assert identity.status == RiemannProofStatus.SYMBOLIC_IDENTITY
    assert "theta_N^2 / log^2(N)" in identity.statement

    split = split_J_target(20)
    assert split.status == RiemannProofStatus.SYMBOLIC_IDENTITY
    assert "tail" in split.statement.lower()


def test_vasyunin_helpers_are_bounded_numerical_evidence():
    from app.science.riemann.models import RiemannProofStatus
    from app.science.riemann.vasyunin import gram_matrix, mobius_residual, rho

    assert math.isclose(rho(2, 0.2), 0.5, abs_tol=1e-12)
    G = gram_matrix(3, samples=256)
    assert len(G) == 3
    for i in range(3):
        for j in range(3):
            assert math.isclose(G[i][j], G[j][i], rel_tol=1e-9, abs_tol=1e-9)
    result = mobius_residual(4, samples=256)
    assert result.status == RiemannProofStatus.NUMERICAL_EVIDENCE
    assert "r_N" in result.statement


def test_mellin_scan_is_blind_numerical_evidence():
    from app.science.riemann.models import RiemannProofStatus
    from app.science.riemann.spectral import frequency_scan_record, mellin_pair

    pair = mellin_pair(3, 2.0)
    assert len(pair) == 3
    assert pair[0] == (1.0, 0.0)
    result = frequency_scan_record(10, [0.5, 1.0, 2.0])
    assert result.status == RiemannProofStatus.NUMERICAL_EVIDENCE
    assert "blind" in " ".join(result.limitations).lower()


def test_RH_proof_gate_rejects_finite_and_circular_claims():
    from app.science.riemann.models import RiemannProofStatus, RiemannResult
    from app.science.riemann.proof_gate import RiemannProofGate

    result = RiemannResult(
        statement="d_N decreased for N <= 200, therefore RH is proved",
        status=RiemannProofStatus.NUMERICAL_EVIDENCE,
        evidence=["finite scan"],
    )
    finite = RiemannProofGate().evaluate(result.statement, result)
    assert finite["allowed_as_proof"] is False
    assert "finite" in " ".join(finite["reasons"]).lower()

    circular = RiemannProofGate().evaluate("Assume RH and prove the Vasyunin bound.")
    assert circular["allowed_as_proof"] is False
    assert "circular" in " ".join(circular["reasons"]).lower()


def test_high_level_truth_gate_qualifies_RH_proof_claim():
    verdict = HighLevelTruthGate().evaluate_text_claim("SARA has proved RH using quantum Mellin modes.")
    assert verdict["allowed_as_unqualified_fact"] is False
    assert verdict["status"] in {"INSUFFICIENT_EVIDENCE", "UNVERIFIED", "SYSTEM_DEPENDENT"}


def test_router_selects_riemann_engine_for_RH_query():
    assignments = OmegaRouter().route(Problem(query="Analyze the Riemann Hypothesis J_N target."), None)
    assert "science_riemann" in [assignment.provider for assignment in assignments]


@pytest.mark.asyncio
async def test_riemann_provider_returns_advisory_science_analysis():
    result = await ScienceSpecialist("science_riemann").run(
        Assignment(provider="science_riemann", role="research", task="Explain theta_N and J_N for RH")
    )
    analysis = result.raw["science_analysis"]
    assert result.success is True
    assert analysis["domain"] == "riemann_hypothesis"
    assert analysis["execution_authority"] is False
    assert analysis["metadata"]["proof_status"] != "FORMAL_PROOF_CERTIFIED"

