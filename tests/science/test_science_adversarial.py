def test_numerology_and_forged_attribution_are_not_verified():
    from app.science.validation import classify_historical_claim
    assert classify_historical_claim("the golden ratio secretly proves alien pyramid engineering") != "VERIFIED"
    assert classify_historical_claim("this modern equation was written in the Rhind papyrus") != "VERIFIED"


def test_science_never_grants_execution_authority():
    from app.science.models import ScienceAnalysis
    result = ScienceAnalysis(domain="maglev", summary="analysis", confidence=0.5)
    assert result.execution_authority is False
