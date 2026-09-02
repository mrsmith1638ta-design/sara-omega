from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def _auth(monkeypatch):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "TEST_TOKEN", "test-action-token")
    monkeypatch.setenv("SARA_RUNTIME_ASSURANCE_SECRET", "unit-test-runtime-assurance-secret")
    return {"Authorization": "Bearer test-action-token"}


def test_chatgpt_action_gateway_requires_bearer_token():
    response = client.post("/gpt/action/gateway", json={"operation": "status"})
    assert response.status_code == 401


def test_chatgpt_action_gateway_reports_runtime_status(monkeypatch):
    response = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={"operation": "status"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "sara-chatgpt-action-gateway"
    assert body["version"] == "3.2.1"
    assert "fail_closed_claim_suppression" == body["runtime_assurance"]["policy"]
    assert "solve" in body["allowed_operations"]


def test_chatgpt_action_gateway_solves_through_sara_omega(monkeypatch):
    response = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={
            "operation": "solve",
            "query": "Analyze data metrics 1 2 3 4.",
            "session_id": "gateway-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "solve"
    assert body["verdict"]["governance"]["disposition"] == "ALLOW"
    assert "data_analytics" in body["verdict"]["providers_used"]


def test_chatgpt_action_gateway_verify_output_fails_closed(monkeypatch):
    response = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={
            "operation": "verify_output",
            "module": "chatgpt-smoke",
            "output": "sara-module-registry is live.",
            "context": {
                "live_module_truth": {
                    "sara-module-registry": {
                        "live": False,
                        "source": "unit-test",
                    }
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "BLOCK"
    assert body["suppression"]["applied"] is True
