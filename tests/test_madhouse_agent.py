from fastapi.testclient import TestClient

import main
from app.madhouse import MadhouseAgent, MadhouseReviewRequest


client = TestClient(main.app)


def _auth(monkeypatch):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "TEST_TOKEN", "test-action-token")
    return {"Authorization": "Bearer test-action-token"}


def test_madhouse_blocks_python_syntax_failures_with_evidence():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-047",
            language="python",
            generated_code="def broken(:\n    return True\n",
            requirements=["Code must parse before promotion."],
        )
    )

    assert result["decision"] == "BLOCKED"
    assert result["promotion_authority"] == "NONE"
    assert result["can_block"] is True
    assert result["can_pass"] is False
    assert result["findings"][0]["class"] == "SYNTAX"
    assert result["findings"][0]["severity"] == "BLOCKING"
    assert result["findings"][0]["reproducible"] is True
    assert result["evidence_ledger"][0]["state"] == "VERIFIED"


def test_madhouse_escalates_recurring_failed_repair_strategy():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-049",
            language="python",
            generated_code="print(session_state)\n",
            previous_failures=[
                {
                    "candidate_id": "build-047",
                    "class": "UNDEFINED_SYMBOL",
                    "fingerprint": "UNDEFINED_SYMBOL:session_state",
                },
                {
                    "candidate_id": "build-048",
                    "class": "UNDEFINED_SYMBOL",
                    "fingerprint": "UNDEFINED_SYMBOL:session_state",
                },
            ],
        )
    )

    assert result["decision"] == "BLOCKED"
    recurring = [finding for finding in result["findings"] if finding["class"] == "RECURRING_FAILURE"]
    assert recurring
    assert recurring[0]["severity"] == "CRITICAL"
    assert recurring[0]["repeat_count"] == 3
    assert result["required_actions"][0] == "Discard the current repair strategy and isolate the root assumption."


def test_madhouse_never_promotes_clean_code_beyond_verification_handoff():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-050",
            language="python",
            generated_code="def add(a, b):\n    return a + b\n",
            requirements=["Return the sum of two values."],
        )
    )

    assert result["decision"] == "READY_FOR_VERIFICATION"
    assert result["promotion_authority"] == "NONE"
    assert result["can_pass"] is False
    assert result["required_validation"] == [
        "compile",
        "static_analysis",
        "unit_tests",
        "integration_tests",
        "security_review",
    ]


def test_madhouse_routes_are_available(monkeypatch):
    health = client.get("/madhouse/health")
    review = client.post(
        "/madhouse/review",
        json={
            "candidate_id": "build-051",
            "language": "python",
            "generated_code": "def bad(:\n    pass\n",
        },
    )
    gateway = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={
            "operation": "madhouse_review",
            "context": {
                "candidate_id": "build-052",
                "language": "python",
                "generated_code": "def bad(:\n    pass\n",
            },
        },
    )

    assert health.status_code == 200
    assert health.json()["service"] == "sara-madhouse-agent"
    assert review.status_code == 200
    assert review.json()["decision"] == "BLOCKED"
    assert gateway.status_code == 200
    assert gateway.json()["service"] == "sara-madhouse-agent"
