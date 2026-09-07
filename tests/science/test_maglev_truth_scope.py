def test_eds_comparison_does_not_expose_system_dependent_behavior_as_boolean():
    from app.science.comparison import compare_levitation_systems

    result = compare_levitation_systems()["EDS"]

    assert result["active_control"] == "SYSTEM_DEPENDENT"
    assert result["passive_restoring_behavior"] == "SYSTEM_DEPENDENT"
    assert result["low_speed_levitation"] == "SYSTEM_DEPENDENT"


def test_hts_transport_passive_restoring_behavior_is_scoped():
    from app.science.comparison import compare_levitation_systems

    result = compare_levitation_systems()["HTS"]

    assert result["passive_restoring_behavior"] == "SYSTEM_DEPENDENT"
    assert "material" in result["dependencies"]
    assert "field history" in result["dependencies"]
    assert "guideway configuration" in result["dependencies"]


def test_eds_characterization_reports_system_dependent_control():
    from app.science.maglev_eds import EDSMaglevEngine

    result = EDSMaglevEngine().characterize(speed_mps=100.0)

    assert result["active_control"] == "SYSTEM_DEPENDENT"
    assert result["passive_restoring_behavior"] == "SYSTEM_DEPENDENT"
    assert result["low_speed_levitation"] == "SYSTEM_DEPENDENT"
