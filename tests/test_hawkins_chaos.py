from fastapi.testclient import TestClient

import main
from app.hawkins_chaos import HawkinsChaosEngine, HawkinsChaosRequest


client = TestClient(main.app)


def _auth(monkeypatch):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "TEST_TOKEN", "test-action-token")
    monkeypatch.setenv("SARA_RUNTIME_ASSURANCE_SECRET", "unit-test-runtime-assurance-secret")
    return {"Authorization": "Bearer test-action-token"}


def test_hawkins_chaos_stable_supported_state_keeps_high_authority():
    result = HawkinsChaosEngine().analyze(
        HawkinsChaosRequest(
            state={"confidence": 0.91, "decision": "APPROVE", "context": {"source": "test"}},
            evidence=[
                {"status": "supported", "confidence": 0.92},
                {"status": "supported", "confidence": 0.89},
                {"status": "supported", "confidence": 0.94},
            ],
            perturbations=21,
            epsilon=0.03,
        )
    )

    assert result["base_decision"] == "ALLOW"
    assert result["effective_authority"] in {"HIGH", "MEDIUM"}
    assert result["hawkins_chaos"]["perturbation_resilience"] >= 0.8
    assert result["effective_confidence"] <= result["base_confidence"]


def test_hawkins_chaos_fragile_state_downgrades_effective_confidence():
    result = HawkinsChaosEngine().analyze(
        HawkinsChaosRequest(
            state={"confidence": 0.8, "decision": "review"},
            evidence=[
                {"status": "supported", "confidence": 0.7},
                {"status": "unsupported", "confidence": 0.4},
            ],
            perturbations=21,
            epsilon=0.12,
        )
    )

    assert result["hawkins_chaos"]["bifurcation_risk"] > 0
    assert result["effective_confidence"] < result["base_confidence"]
    assert result["effective_authority"] in {"LOW", "MEDIUM"}


def test_hawkins_chaos_enterprise_route_is_available():
    health = client.get("/hawkins-chaos/health")
    analysis = client.post(
        "/hawkins-chaos/analyze",
        json={"state": {"confidence": 0.91}, "evidence": [{"status": "supported"}]},
    )

    assert health.status_code == 200
    assert health.json()["service"] == "sara-hawkins-chaos-dynamics"
    assert analysis.status_code == 200
    assert "hawkins_chaos" in analysis.json()


def test_chatgpt_gateway_exposes_hawkins_chaos(monkeypatch):
    response = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={
            "operation": "hawkins_chaos",
            "query": "Should SARA approve this deployment?",
            "context": {"confidence": 0.91, "decision": "APPROVE"},
            "evidence": [{"status": "supported"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["service"] == "sara-hawkins-chaos-dynamics"


def test_chatgpt_gateway_solve_returns_hawkins_chaos(monkeypatch):
    response = client.post(
        "/gpt/action/gateway",
        headers=_auth(monkeypatch),
        json={
            "operation": "solve",
            "query": "Analyze data metrics 1 2 3 4.",
            "session_id": "hawkins-gateway-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["governance"]["disposition"] == "ALLOW"
    assert body["hawkins_chaos"]["policy"] == "stability_adjustment_only"
