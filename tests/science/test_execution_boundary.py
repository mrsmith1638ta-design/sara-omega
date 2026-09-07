def test_science_output_is_reasoning_only():
    from app.science.models import ScienceAnalysis
    assert ScienceAnalysis(domain="engineering", summary="x", confidence=0.1).execution_authority is False
