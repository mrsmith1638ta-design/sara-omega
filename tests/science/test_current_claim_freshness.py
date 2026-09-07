from datetime import date, timedelta


def test_current_technology_claim_requires_fresh_review():
    from app.science.validation import current_claim_status
    assert current_claim_status(date.today() - timedelta(days=400), max_age_days=365) == "CURRENTLY_INACCESSIBLE"
    assert current_claim_status(date.today() - timedelta(days=30), max_age_days=365) == "SUPPORTED"
