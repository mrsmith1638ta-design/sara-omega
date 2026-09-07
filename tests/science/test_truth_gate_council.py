def test_provider_consensus_does_not_raise_certainty_ceiling():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="Multiple providers agree this EDS family behavior is universal.",
        provenance_class=ProvenanceClass.ENGINEERING_MODEL,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.FAMILY_LEVEL,
        certainty_level=CertaintyLevel.VERIFIED,
        dependency_conditions=["guideway topology"],
        source_ids=["provider.a", "provider.b", "provider.c"],
        universality_status=UniversalityStatus.UNIVERSAL_SUPPORTED,
        certainty_ceiling=CertaintyLevel.INFERRED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.gated_certainty == CertaintyLevel.INFERRED
    assert decision.universality_status == UniversalityStatus.SYSTEM_DEPENDENT
