from fastapi.testclient import TestClient

import main
from app.epistemic import EpistemicAgent, EpistemicReviewRequest


client = TestClient(main.app)


def _claim(text: str, evidence_ids: list[str]) -> dict[str, object]:
    return {"claim_id": "tests", "text": text, "evidence_ids": evidence_ids}


def _evidence(evidence_id: str = "test-ci-validation", detail: str = "293 repository tests passed in validation run 123"):
    return {
        "id": evidence_id,
        "status": "PASS",
        "evidenceState": "VERIFIED",
        "detail": detail,
        "source": "https://github.com/example/run/123",
        "hash": "a" * 64,
    }


def test_epistemic_narrows_broad_production_test_claim_to_repository_scope():
    result = EpistemicAgent().review(
        EpistemicReviewRequest(
            candidate_id="a" * 40,
            claims=[_claim("All production tests passed.", ["test-ci-validation"])],
            evidence=[_evidence()],
        )
    )

    assert result["decision"] == "BLOCKED"
    audited = result["claims"][0]
    assert audited["state"] == "OVERSTATED"
    assert audited["corrected_claim"] == "293 repository tests passed in validation run 123."
    assert result["can_pass"] is False
    assert result["promotion_authority"] == "NONE"


def test_epistemic_blocks_claim_contradicted_by_evidence():
    result = EpistemicAgent().review(
        EpistemicReviewRequest(
            candidate_id="b" * 40,
            claims=[_claim("Production acceptance passed.", ["production-attestation"])],
            evidence=[{**_evidence("production-attestation"), "status": "UNVERIFIED", "evidenceState": "UNVERIFIED"}],
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["claims"][0]["state"] == "CONTRADICTED"


def test_epistemic_accepts_explicitly_scoped_claim_without_promotion_authority():
    result = EpistemicAgent().review(
        EpistemicReviewRequest(
            candidate_id="c" * 40,
            claims=[_claim("293 repository tests passed in validation run 123.", ["test-ci-validation"])],
            evidence=[_evidence()],
        )
    )

    assert result["decision"] == "READY_FOR_VERIFICATION"
    assert result["claims"][0]["state"] == "SUPPORTED"
    assert result["can_pass"] is False
    assert result["execution_authority"] == "NONE"


def test_epistemic_route_is_available():
    response = client.post(
        "/epistemic/review",
        json={
            "candidate_id": "d" * 40,
            "claims": [_claim("293 repository tests passed in validation run 123.", ["test-ci-validation"])],
            "evidence": [_evidence()],
        },
    )

    assert response.status_code == 200
    assert response.json()["service"] == "sara-epistemic-agent"
