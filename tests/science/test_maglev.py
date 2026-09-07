import pytest


def test_ems_validates_gap_and_computes_drag_power():
    from app.science.maglev_ems import EMSMaglevEngine
    from app.science.validation import ScienceValidationError
    e = EMSMaglevEngine()
    out = e.aero_state(rho=1.225, cd=0.16, area=10.0, velocity=600/3.6)
    assert out["drag_force_n"] > 0
    assert out["drag_power_w"] > out["drag_force_n"]
    with pytest.raises(ScienceValidationError):
        e.simplified_lift(turns=100, current=10, area=0.1, gap=0)


def test_eds_and_hts_keep_maturity_and_physics_distinct():
    from app.science.maglev_eds import EDSMaglevEngine
    from app.science.maglev_hts import HTSMaglevEngine
    eds = EDSMaglevEngine().characterize(speed_mps=100)
    hts = HTSMaglevEngine().characterize(temperature_k=77, critical_current_density=1e8)
    assert eds["family"] == "EDS"
    assert eds["provenance_class"] in {"ESTABLISHED_PHYSICS", "ENGINEERING_MODEL"}
    assert hts["family"] == "HTS"
    assert hts["provenance_class"] == "EXPERIMENTAL_TECHNOLOGY"


def test_comparison_exposes_scoped_control_and_stability_tradeoffs():
    from app.science.comparison import compare_levitation_systems
    result = compare_levitation_systems()
    assert set(result) == {"EMS", "EDS", "HTS"}
    assert result["EMS"]["active_control"] == "REQUIRED"
    assert result["EDS"]["active_control"] == "SYSTEM_DEPENDENT"
    assert result["EDS"]["passive_restoring_behavior"] == "SYSTEM_DEPENDENT"
    assert result["HTS"]["passive_restoring_behavior"] == "SYSTEM_DEPENDENT"
