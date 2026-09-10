import math
import json

import pytest

from app.science.historical_nuclear_fusion import (
    benchmark_historical_fusion,
    historical_fusion_decay,
    madhouse_challenge,
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
