import asyncio


def test_science_specialist_attaches_truth_gate_metadata():
    from app.models import Assignment
    from app.science.provider import ScienceSpecialist

    result = asyncio.run(
        ScienceSpecialist("science_maglev_eds").run(
            Assignment(provider="science_maglev_eds", role="specialist", task="Compare EDS control and stability.")
        )
    )

    analysis = result.raw["science_analysis"]
    gate = analysis["metadata"]["truth_gate"]
    assert gate["claims"]
    assert gate["decisions"]
    assert any(item["universality_status"] == "SYSTEM_DEPENDENT" for item in gate["decisions"])
    assert analysis["execution_authority"] is False
