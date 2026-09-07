import pytest


def test_family_scoped_claim_cannot_be_universal_verified():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="All EDS maglev systems are passively stable.",
        provenance_class=ProvenanceClass.ENGINEERING_MODEL,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.FAMILY_LEVEL,
        certainty_level=CertaintyLevel.VERIFIED,
        dependency_conditions=["guideway topology", "damping method"],
        source_ids=["maglev.eds"],
        universality_status=UniversalityStatus.UNIVERSAL_SUPPORTED,
        certainty_ceiling=CertaintyLevel.SUPPORTED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.disposition == "QUALIFIED"
    assert decision.gated_certainty == CertaintyLevel.SUPPORTED
    assert decision.universality_status == UniversalityStatus.SYSTEM_DEPENDENT


def test_missing_required_dependencies_fail_closed():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="This HTS transport configuration has passive restoring stability.",
        provenance_class=ProvenanceClass.EXPERIMENTAL_TECHNOLOGY,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.CONFIGURATION_SPECIFIC,
        certainty_level=CertaintyLevel.SUPPORTED,
        dependency_conditions=[],
        source_ids=["maglev.hts"],
        universality_status=UniversalityStatus.SYSTEM_DEPENDENT,
        certainty_ceiling=CertaintyLevel.SUPPORTED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.disposition == "QUALIFIED"
    assert decision.universality_status == UniversalityStatus.INSUFFICIENT_EVIDENCE
    assert decision.gated_certainty in {CertaintyLevel.UNVERIFIED, CertaintyLevel.UNKNOWN}


def test_certainty_cannot_exceed_ceiling():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="A modeled EDS response is established physics for this vehicle.",
        provenance_class=ProvenanceClass.ENGINEERING_MODEL,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.ARCHITECTURE_SPECIFIC,
        certainty_level=CertaintyLevel.VERIFIED,
        dependency_conditions=["guideway topology"],
        source_ids=["maglev.eds"],
        universality_status=UniversalityStatus.SYSTEM_DEPENDENT,
        certainty_ceiling=CertaintyLevel.INFERRED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.gated_certainty == CertaintyLevel.INFERRED
    assert decision.disposition == "QUALIFIED"


def test_missing_sources_cannot_remain_supported():
    from app.science.models import (
        ApplicabilityScope,
        CertaintyLevel,
        ProvenanceClass,
        ScienceClaim,
        UniversalityStatus,
    )
    from app.science.truth_gate import HighLevelTruthGate

    claim = ScienceClaim(
        claim_text="An unsupported historical assertion.",
        provenance_class=ProvenanceClass.HISTORICALLY_COMPATIBLE_RECONSTRUCTION,
        evidence_status="SUPPORTED",
        applicability_scope=ApplicabilityScope.HISTORICAL_RECONSTRUCTION,
        certainty_level=CertaintyLevel.SUPPORTED,
        dependency_conditions=["historical source"],
        source_ids=[],
        universality_status=UniversalityStatus.SYSTEM_DEPENDENT,
        certainty_ceiling=CertaintyLevel.SUPPORTED,
    )

    decision = HighLevelTruthGate().evaluate_claim(claim)

    assert decision.gated_certainty in {CertaintyLevel.UNVERIFIED, CertaintyLevel.UNKNOWN}
    assert decision.universality_status == UniversalityStatus.INSUFFICIENT_EVIDENCE
