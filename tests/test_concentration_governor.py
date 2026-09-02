from fastapi.testclient import TestClient

import main
from app.concentration import ConcentrationGovernor, ConcentrationRequest


client = TestClient(main.app)


def _auth(monkeypatch):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "TEST_TOKEN", "test-action-token")
    monkeypatch.setenv("SARA_RUNTIME_ASSURANCE_SECRET", "unit-test-runtime-assurance-secret")
    return {"Authorization": "Bearer test-action-token"}


def test_concentration_governor_accepts_focused_engineering_output():
    result = ConcentrationGovernor().analyze(
        ConcentrationRequest(
            objective="Integrate a formula that prevents AI deviation in code programming.",
            output="Integrate objective lock code, test the formula, and verify the gateway output.",
            constraints=["code programming", "prevent AI deviation", "verify"],
        )
    )

    assert result["focus_score"] >= result["threshold"]
    assert result["render_instruction"] == "render"


def test_concentration_governor_demands_refocus_for_drift():
    result = ConcentrationGovernor().analyze(
        ConcentrationRequest(
            objective="Fix code concentration and prevent AI deviation.",
            output="This is a broad philosophical story about intelligence and branding.",
            constraints=["code", "fix", "prevent deviation"],
        )
    )

    assert result["focus_score"] < result["threshold"]
    assert result["refocus_required"] is True
    assert result["render_instruction"] == "refocus_before_final"


def test_concentration_enterprise_route_is_available():
    health = client.get("/concentration/health")
    analysis = client.post(
        "/concentration/analyze",
        json={
            "objective": "Integrate concentration governor.",
            "output": "Integrate concentration governor with tests.",
        },
    )

    assert health.status_code == 200
    assert health.json()["service"] == "sara-concentration-governor"
    assert analysis.status_code == 200
    assert analysis.json()["policy"] == "objective_lock_deviation_control"


def test_chatgpt_gateway_exposes_concentration(monkeypatch):
    response = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={
            "operation": "concentration",
            "objective": "Keep SARA focused on code programming.",
            "output": "Keep SARA focused on code programming with objective lock tests.",
            "context": {"constraints": ["code programming", "objective lock"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["service"] == "sara-concentration-governor"


def test_chatgpt_gateway_solve_returns_concentration_governor(monkeypatch):
    response = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={
            "operation": "solve",
            "query": "Analyze data metrics 1 2 3 4.",
            "session_id": "concentration-gateway-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["governance"]["disposition"] == "ALLOW"
    assert body["concentration_governor"]["policy"] == "objective_lock_deviation_control"
