def test_stale_current_claim_cannot_remain_verified():
    from app.science.models import ApplicabilityScope, CertaintyLevel, ProvenanceClass, ScienceClaim, UniversalityStatus
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="This experimental system is currently deployed.",
        provenance_class=ProvenanceClass.EXPERIMENTAL_TECHNOLOGY,
        evidence_status="STALE",
        applicability_scope=ApplicabilityScope.EXPERIMENTAL_OBSERVATION,
        certainty_level=CertaintyLevel.VERIFIED,
        dependency_conditions=["current deployment evidence"],
        source_ids=["historical.test.record"],
        universality_status=UniversalityStatus.SYSTEM_DEPENDENT,
        certainty_ceiling=CertaintyLevel.SUPPORTED,
    )
    decision = HighLevelTruthGate().evaluate_claim(claim)
    assert decision.gated_certainty in {CertaintyLevel.UNVERIFIED, CertaintyLevel.UNKNOWN}
