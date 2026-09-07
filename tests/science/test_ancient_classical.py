import math


def test_giza_seked_is_5_5_and_modern_angle_is_separate_provenance():
    from app.science.ancient_egypt import AncientEgyptEngine
    result = AncientEgyptEngine().seked(440, 280)
    assert result["seked_palms"] == 5.5
    assert math.isclose(result["face_angle_degrees"], math.degrees(math.atan(280/220)), rel_tol=1e-9)
    assert result["seked_provenance"] == "HISTORICALLY_COMPATIBLE_RECONSTRUCTION"
    assert result["angle_provenance"] == "MODERN_ENGINEERING_DERIVATION"


def test_egyptian_frustum_volume():
    from app.science.ancient_egypt import AncientEgyptEngine
    assert AncientEgyptEngine().frustum_volume(6, 4, 2) == 56


def test_vitruvian_ratios_and_arch_geometry():
    from app.science.classical_greek_roman import ClassicalGreekRomanEngine
    engine = ClassicalGreekRomanEngine()
    assert engine.column_height("ionic", 2.0) == 18.0
    assert engine.eustyle_spacing(2.0, central=False) == 4.5
    assert engine.eustyle_spacing(2.0, central=True) == 6.0
    arch = engine.semicircular_arch(5.0)
    assert math.isclose(arch["radius"], 2.5)
    assert math.isclose(arch["arc_length"], math.pi * 2.5)


def test_secret_pyramid_formula_is_not_promoted_to_fact():
    from app.science.ancient_egypt import AncientEgyptEngine
    result = AncientEgyptEngine().classify_claim("secret pyramid formula")
    assert result == "UNVERIFIED_RECONSTRUCTION"
