def test_final_synthesis_overstatement_is_detected():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="EDS low-speed levitation behavior depends on system architecture.",
        provenance_class=ProvenanceClass.ENGINEERING_MODEL,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.FAMILY_LEVEL,
        certainty_level=CertaintyLevel.SUPPORTED,
        dependency_conditions=["guideway topology", "transition strategy"],
        source_ids=["maglev.eds"],
        universality_status=UniversalityStatus.SYSTEM_DEPENDENT,
        certainty_ceiling=CertaintyLevel.SUPPORTED,
    )

    verdict = HighLevelTruthGate().evaluate_final_synthesis(
        "EDS never levitates at low speed.",
        [claim],
    )

    assert verdict["allowed"] is False
    assert verdict["status"] == "SYSTEM_DEPENDENT"
