from app.expert_reasoning import ExpertReasoningFabric
from app.unified_fusion import health


def test_expert_fabric_never_claims_consciousness_or_credentials():
    fabric = ExpertReasoningFabric()
    state = fabric.health()

    assert state["claims_human_credentials"] is False
    assert state["claims_human_consciousness"] is False
    assert state["claims_ai_consciousness"] is False
    assert state["execution_authority"] is False
    assert state["release_authority"] is False


def test_relevant_advanced_methods_are_selected_without_blanket_fanout():
    fabric = ExpertReasoningFabric()
    result = fabric.synthesize(
        "Assess an AI training platform contract for a university workforce program.",
        evidence=[{"id": "e1"}],
    )

    assert "phd-research" in result["selected_lens_ids"]
    assert "jd-legal" in result["selected_lens_ids"]
    assert "edd-applied" in result["selected_lens_ids"]
    assert "ai-research-phd" in result["selected_lens_ids"]
    assert "education" in result["industry_lenses"]
    assert result["simulated_expert_output_is_not_evidence"] is True


def test_dynamic_industry_lens_accepts_industries_not_in_static_catalog():
    fabric = ExpertReasoningFabric()
    result = fabric.synthesize(
        "Evaluate process risk.",
        industries=["Semiconductor Manufacturing"],
    )

    assert "semiconductor_manufacturing" in result["industry_lenses"]
    assert "industry-semiconductor_manufacturing" in result["selected_lens_ids"]


def test_unified_health_exposes_expert_reasoning_boundaries():
    state = health()

    assert state["expert_reasoning_fabric"] is True
    assert state["phd_research_methodology"] is True
    assert state["jd_legal_reasoning_methodology"] is True
    assert state["edd_applied_education_methodology"] is True
    assert state["ai_research_phd_methodology"] is True
    assert state["dynamic_cross_industry_reasoning"] is True
    assert state["claims_human_consciousness"] is False
    assert state["claims_ai_consciousness"] is False
    assert state["credential_impersonation"] is False
