from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_enterprise_runtime_router_exposes_health_surfaces():
    runtime = client.get("/runtime-assurance/health")
    modules = client.get("/module-awareness/health")
    titan = client.get("/titan/health")

    assert runtime.status_code == 200
    assert runtime.json()["policy"] == "fail_closed_claim_suppression"
    assert modules.status_code == 200
    assert modules.json()["service"] == "sara-module-awareness-integrated"
    assert titan.status_code == 200
    assert titan.json()["service"] == "sara-titan-integrated"
