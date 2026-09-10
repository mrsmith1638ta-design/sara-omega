from app.road_gates import RoadGateAgent, RoadGateReviewRequest
from fastapi.testclient import TestClient
import main


SHA = "a" * 40
client = TestClient(main.app)


def snapshot(**overrides):
    value = {
        "source_commit_sha": SHA,
        "production_accepted": True,
        "failsafe_configured": True,
        "root_on_dedicated_mount": True,
        "persistence_observed_across_boots": True,
        "persistence_status": "PROVEN",
        "chain_valid": True,
        "checkpoint_self_test": True,
        "bootstrap_ready": True,
    }
    value.update(overrides)
    return value


def request(**overrides):
    value = {
        "candidate_id": SHA,
        "production": snapshot(),
        "observations": [
            {"id": "contextdev-authorization", "status": "PASS", "source": "context-dev"},
            {"id": "madhouse-adversarial-review", "status": "PASS", "source": "madhouse"},
            {"id": "epistemic-claim-audit", "status": "PASS", "source": "epistemic"},
            {"id": "test-ci-validation", "status": "PASS", "source": "github"},
            {"id": "production-attestation", "status": "PASS", "source": "railway"},
        ],
        "providers": ["railway", "github-actions"],
        "probe_ms": 120,
    }
    value.update(overrides)
    return RoadGateReviewRequest(**value)


def test_all_road_gate_evidence_is_exact_sha_bound_and_passes_from_concrete_observations():
    result = RoadGateAgent().review(request())

    assert result["decision"] == "READY_FOR_VERIFICATION"
    assert {item["gate"] for item in result["gates"]} == {"GOVERNANCE", "PRIVACY", "PERFORMANCE", "RECOVERY", "MULTI-CLOUD"}
    assert all(item["status"] == "PASS" for item in result["gates"])
    assert result["can_pass"] is False


def test_multi_cloud_does_not_pass_from_railway_alone():
    result = RoadGateAgent().review(request(providers=["railway"]))

    multi_cloud = next(item for item in result["gates"] if item["gate"] == "MULTI-CLOUD")
    assert multi_cloud["status"] == "UNVERIFIED"
    assert result["decision"] == "BLOCKED"


def test_wrong_candidate_sha_blocks_every_gate_artifact():
    result = RoadGateAgent().review(request(candidate_id="b" * 40))

    assert result["decision"] == "BLOCKED"
    assert all(item["status"] == "UNVERIFIED" for item in result["gates"])


def test_road_gate_route_exposes_live_runtime_evidence_contract(monkeypatch):
    monkeypatch.setattr(main, "production_acceptance_snapshot", lambda: snapshot())
    response = client.post(
        "/road/gates/review",
        json={"candidate_id": SHA, "observations": request().observations, "providers": ["railway", "github-actions"], "probe_ms": 120},
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "READY_FOR_VERIFICATION"
