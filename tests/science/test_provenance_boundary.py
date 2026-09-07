def test_giza_dimension_match_does_not_become_documented_ancient():
    from app.science.validation import provenance_for_reconstruction
    assert provenance_for_reconstruction(direct_primary_source=False) == "HISTORICALLY_COMPATIBLE_RECONSTRUCTION"
