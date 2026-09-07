import pytest


def test_science_router_is_selective():
    from app.science.router import ScienceRouter
    r = ScienceRouter()
    assert "ancient_egypt" in r.route_text("calculate the seked of the Great Pyramid")
    assert "classical_greek_roman" in r.route_text("compare Ionic and Corinthian columns")
    maglev = set(r.route_text("compare EMS EDS and HTS maglev at high speed"))
    assert {"maglev_ems", "maglev_eds", "maglev_hts"}.issubset(maglev)
    assert r.route_text("help me rewrite a resume") == []


@pytest.mark.asyncio
async def test_science_engines_are_advisory_and_council_cannot_be_disabled():
    from app.models import Problem, CANONICAL_COUNCIL_STAGE_ORDER
    from app.orchestrator import SaraOmega

    sara = SaraOmega()
    verdict = await sara.solve(Problem(query="What is the Egyptian seked for a 440 by 280 cubit pyramid?", council=False))
    assert verdict.council_trace.mandatory is True
    assert verdict.council_trace.completed == list(CANONICAL_COUNCIL_STAGE_ORDER)
