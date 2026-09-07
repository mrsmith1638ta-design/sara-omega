import pytest


def test_science_contracts_and_units_are_fail_closed():
    from app.science.models import ProvenanceClass, ScienceAnalysis, ScienceCalculation
    from app.science.validation import ScienceValidationError, require_positive

    assert ProvenanceClass.DOCUMENTED_ANCIENT.value == "DOCUMENTED_ANCIENT"
    calc = ScienceCalculation(
        equation_id="drag_force",
        variables={"v": "velocity"},
        units={"v": "m/s", "result": "N"},
        inputs={"v": 10.0},
        result=5.0,
        provenance_class=ProvenanceClass.ESTABLISHED_PHYSICS,
        evidence_status="SUPPORTED",
        assumptions=["steady flow"],
        limitations=["simplified"],
        source_ids=["physics.drag"],
        validation_status="VALID",
    )
    analysis = ScienceAnalysis(domain="engineering", summary="ok", calculations=[calc], confidence=0.8)
    assert analysis.execution_authority is False
    assert analysis.model_dump()["calculations"][0]["equation_id"] == "drag_force"
    with pytest.raises(ScienceValidationError):
        require_positive("mass", 0)


def test_unit_dimension_validation_rejects_mismatch():
    from app.science.units import UnitDimensionError, validate_dimensions

    validate_dimensions("m", "m")
    with pytest.raises(UnitDimensionError):
        validate_dimensions("m", "s")
