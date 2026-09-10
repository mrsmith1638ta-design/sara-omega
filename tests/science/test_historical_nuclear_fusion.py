import math
import json

import pytest

from app.science.historical_nuclear_fusion import (
    benchmark_historical_fusion,
    comparative_algorithm_laboratory,
    euler_decay_chain,
    historical_fusion_decay,
    matrix_exponential_decay_chain,
    madhouse_challenge,
    monte_carlo_uncertainty,
    rk4_decay_chain,
)


def test_science_router_selects_historical_nuclear_fusion():
    from app.science.router import ScienceRouter

    assert "historical_nuclear_fusion" in ScienceRouter().route_text(
        "benchmark Egyptian mathematics with Laplace nuclear decay-chain calculations"
    )


def test_historical_fusion_preserves_decay_chain_nonnegativity_and_mass_flow():
    result = historical_fusion_decay([1.0, 0.0, 0.0], [0.1, 0.2], 2.0)

    assert len(result) == 3
    assert all(value >= -1e-12 for value in result)
    assert math.isclose(sum(result), 1.0, rel_tol=0.0, abs_tol=2e-6)
    assert result[1] > 0.0
    assert result[2] > 0.0


def test_historical_fusion_matches_modern_rk4_reference():
    fused = historical_fusion_decay([1.0, 0.0], [0.7], 1.5)
    reference = rk4_decay_chain([1.0, 0.0], [0.7], 1.5, steps=12000)

    assert max(abs(left - right) for left, right in zip(fused, reference)) < 2e-4


def test_comparative_methods_agree_on_controlled_decay_chain():
    initial = [1.0, 0.0, 0.0]
    rates = [0.3, 0.15]
    duration = 2.0

    expected = matrix_exponential_decay_chain(initial, rates, duration)
    for candidate in (
        historical_fusion_decay(initial, rates, duration),
        rk4_decay_chain(initial, rates, duration, steps=4000),
        euler_decay_chain(initial, rates, duration, steps=4000),
    ):
        assert max(abs(left - right) for left, right in zip(candidate, expected)) < 2e-3


def test_laboratory_reports_claims_and_monte_carlo_uncertainty():
    report = comparative_algorithm_laboratory(samples=8, seed=4, uncertainty_samples=16)

    assert report["problem_class"] == "stable_terminal_decay_chain"
    assert set(report["methods"]) == {"egyptian_dyadic", "euler", "rk4", "matrix_exponential"}
    assert report["methods"]["egyptian_dyadic"]["max_absolute_error"] >= 0.0
    assert report["uncertainty"]["samples"] == 16
    assert report["claims"]["numerical_advantage"]["status"] in {"SUPPORTED", "UNSUPPORTED"}
    assert report["madhouse"]["can_pass"] is False


def test_monte_carlo_uncertainty_is_reproducible_and_bounded():
    result = monte_carlo_uncertainty([1.0, 0.0], [0.4], 1.5, samples=12, seed=9)

    assert result["samples"] == 12
    assert result["mean"][0] >= 0.0
    assert result["standard_deviation"][0] >= 0.0


def test_benchmark_reports_historical_provenance_and_madhouse_result():
    report = benchmark_historical_fusion(samples=24, seed=7)

    assert report["algorithm"] == "egyptian-dyadic-bateman-fusion"
    assert report["provenance"]["egyptian"]
    assert report["provenance"]["eighteenth_century"]
    assert report["madhouse"]["decision"] == "READY_FOR_VERIFICATION"
    assert report["madhouse"]["can_pass"] is False
    assert report["samples"] == 24


def test_madhouse_challenge_blocks_broken_candidate():
    result = madhouse_challenge("def candidate():\n    return missing_value\n")

    assert result["decision"] == "BLOCKED"
    assert result["can_pass"] is False


@pytest.mark.asyncio
async def test_sara_science_provider_returns_fused_analysis_with_truth_metadata():
    from app.models import Assignment
    from app.science.provider import ScienceSpecialist

    result = await ScienceSpecialist("science_historical_nuclear_fusion").run(Assignment(
        provider="science_historical_nuclear_fusion", role="research", task="fuse Egyptian and Laplace nuclear mathematics"
    ))
    analysis = json.loads(result.answer)
    assert analysis["domain"] == "historical_nuclear_fusion"
    assert analysis["execution_authority"] is False
    assert analysis["metadata"]["truth_gate"]["decisions"]
