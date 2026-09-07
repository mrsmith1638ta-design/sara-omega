def test_historical_reconstruction_cannot_be_promoted_to_documented_ancient():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="Khufu's builders are documented using the Rhind seked procedure at Giza.",
        provenance_class=ProvenanceClass.HISTORICALLY_COMPATIBLE_RECONSTRUCTION,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.HISTORICAL_RECONSTRUCTION,
        certainty_level=CertaintyLevel.VERIFIED,
        dependency_conditions=["direct Old Kingdom source"],
        source_ids=["egypt.seked"],
        universality_status=UniversalityStatus.SYSTEM_DEPENDENT,
        certainty_ceiling=CertaintyLevel.INFERRED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.gated_certainty == CertaintyLevel.INFERRED
    assert decision.disposition == "QUALIFIED"


def test_model_claim_cannot_be_promoted_to_established_physics():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="This modeled EDS configuration proves all EDS systems behave this way.",
        provenance_class=ProvenanceClass.ENGINEERING_MODEL,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.ARCHITECTURE_SPECIFIC,
        certainty_level=CertaintyLevel.VERIFIED,
        dependency_conditions=["guideway topology", "magnet architecture"],
        source_ids=["maglev.eds"],
        universality_status=UniversalityStatus.UNIVERSAL_SUPPORTED,
        certainty_ceiling=CertaintyLevel.INFERRED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.gated_certainty == CertaintyLevel.INFERRED
    assert decision.universality_status == UniversalityStatus.SYSTEM_DEPENDENT
