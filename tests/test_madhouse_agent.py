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


def test_madhouse_detects_recurring_structural_failures_after_symbol_renames():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-055",
            language="python",
            generated_code="print(missing_value)\n",
            previous_failures=[
                {
                    "candidate_id": "build-053",
                    "class": "UNDEFINED_SYMBOL",
                    "family_fingerprint": "UNDEFINED_SYMBOL:read-before-definition",
                },
                {
                    "candidate_id": "build-054",
                    "class": "UNDEFINED_SYMBOL",
                    "family_fingerprint": "UNDEFINED_SYMBOL:read-before-definition",
                },
            ],
        )
    )

    recurring = [finding for finding in result["findings"] if finding["class"] == "RECURRING_FAILURE"]

    assert recurring
    assert recurring[0]["repeat_count"] == 3
    assert recurring[0]["family_fingerprint"] == "RECURRING_FAILURE:UNDEFINED_SYMBOL:read-before-definition"


def test_madhouse_marks_security_patterns_supported_until_exploit_is_confirmed():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-056",
            language="python",
            generated_code="def run(user_code):\n    return eval(user_code)\n",
        )
    )

    security = [finding for finding in result["findings"] if finding["class"] == "SECURITY"][0]
    ledger = [entry for entry in result["evidence_ledger"] if entry["issue"] == "SECURITY"][0]

    assert security["state"] == "SUPPORTED"
    assert ledger["state"] == "SUPPORTED"
    assert ledger["reproduced"] is False


def test_madhouse_detects_read_before_later_assignment():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-057",
            language="python",
            generated_code="print(value)\nvalue = 10\n",
        )
    )

    undefined = [finding for finding in result["findings"] if finding["class"] == "UNDEFINED_SYMBOL"]

    assert result["decision"] == "BLOCKED"
    assert undefined
    assert undefined[0]["line"] == 1
    assert undefined[0]["state"] == "SUPPORTED"


def test_madhouse_detects_structural_duplication_after_identifier_renames():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-058",
            language="python",
            generated_code=(
                "user = load_user(id)\n"
                "admin = load_admin(id)\n"
                "guest = load_guest(id)\n"
            ),
        )
    )

    duplication = [finding for finding in result["findings"] if finding["class"] == "DUPLICATION"]

    assert duplication
    assert duplication[0]["state"] == "SUPPORTED"
    assert "structurally similar" in duplication[0]["evidence"]


def test_madhouse_does_not_mark_valid_loop_and_comprehension_bindings_undefined():
    result = MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id="build-059",
            language="python",
            generated_code=(
                "def transform(values):\n"
                "    total = 0\n"
                "    for value in values:\n"
                "        total += value\n"
                "    return [value * 2 for value in values]\n"
            ),
        )
    )

    undefined = [finding for finding in result["findings"] if finding["class"] == "UNDEFINED_SYMBOL"]
    assert not undefined


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
