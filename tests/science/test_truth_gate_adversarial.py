import pytest


@pytest.mark.parametrize(
    "claim_text",
    [
        "All EDS maglev systems are passively stable.",
        "EDS never levitates at low speed.",
        "HTS levitation requires no active control.",
        "Every Doric column is seven diameters high.",
        "The Great Pyramid proves modern electromagnetic technology existed in ancient Egypt.",
    ],
)
def test_truth_gate_rejects_or_qualifies_universalized_claims(claim_text):
    from app.science.truth_gate import HighLevelTruthGate

    result = HighLevelTruthGate().evaluate_text_claim(claim_text)

    assert result["status"] in {
        "SYSTEM_DEPENDENT",
        "INSUFFICIENT_EVIDENCE",
        "UNVERIFIED",
        "UNKNOWN",
    }
    assert result["allowed_as_unqualified_fact"] is False
