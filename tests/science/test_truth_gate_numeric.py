def test_engineering_defaults_are_not_user_specific_results():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="The vehicle's drag force is 12250 N.",
        provenance_class=ProvenanceClass.MODERN_ENGINEERING_DERIVATION,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.CONFIGURATION_SPECIFIC,
        certainty_level=CertaintyLevel.SUPPORTED,
        dependency_conditions=["rho", "Cd", "area", "velocity"],
        source_ids=["engineering.drag"],
        assumptions=["Illustrative default values used"],
        limitations=["User-specific geometry was not supplied"],
        universality_status=UniversalityStatus.SYSTEM_DEPENDENT,
        certainty_ceiling=CertaintyLevel.INFERRED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.gated_certainty == CertaintyLevel.INFERRED
    assert decision.disposition == "QUALIFIED"
