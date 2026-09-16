import pytest
from fastapi.testclient import TestClient


def test_default_app_factory_disables_local_operator_without_explicit_opt_in(monkeypatch, tmp_path):
    from sara_unified.app import create_app

    monkeypatch.delenv("SARA_ALLOW_LOCAL_OPERATOR", raising=False)
    monkeypatch.setenv("SARA_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    client = TestClient(create_app())
    response = client.post(
        "/v1/recovery/restart",
        headers={"Authorization": "Bearer local-operator"},
        json={"context": {"service": "api"}, "approved": True},
    )
    assert response.status_code == 401


def test_api_rejects_requests_over_configured_size_limit(monkeypatch, tmp_path):
    from sara_unified.app import create_app

    monkeypatch.setenv("SARA_ALLOW_LOCAL_OPERATOR", "true")
    monkeypatch.setenv("SARA_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("SARA_MAX_REQUEST_BYTES", "32")
    client = TestClient(create_app())
    response = client.post(
        "/v1/jury/deliberate",
        json={"opinions": [{"model_id": "m" * 40, "conclusion": "x", "confidence": 0.5}]},
    )
    assert response.status_code == 413


def test_provenance_registry_rejects_digest_mismatch():
    from sara_unified.evidence.provenance import ProvenanceRegistry
    registry=ProvenanceRegistry()
    record=registry.record("doc", b"abc", source="unit")
    assert registry.verify(record.record_id, b"abc")
    assert not registry.verify(record.record_id, b"abd")


def test_structured_telemetry_redacts_sensitive_fields():
    from sara_unified.adapters.telemetry import StructuredTelemetry
    event=StructuredTelemetry().event("x", {"token":"secret", "nested":{"password":"p", "ok":1}})
    assert event["attributes"]["token"] == "[REDACTED]"
    assert event["attributes"]["nested"]["password"] == "[REDACTED]"
    assert event["attributes"]["nested"]["ok"] == 1


def test_key_value_storage_is_namespaced_and_copy_safe():
    from sara_unified.adapters.storage import MemoryStorage
    storage=MemoryStorage()
    value={"x":[1]}; storage.put("tenant-a","k",value); value["x"].append(2)
    assert storage.get("tenant-a","k") == {"x":[1]}
    assert storage.get("tenant-b","k") is None


def test_capability_passport_api_is_signed_and_verifiable(tmp_path):
    from sara_unified.app import SARAUnified
    client=TestClient(SARAUnified.local(tmp_path/"audit.jsonl").api)
    response=client.get("/v1/passports/evidence-fusion")
    assert response.status_code == 200
    body=response.json()
    assert body["passport"]["capability_id"] == "evidence-fusion"
    assert body["signature_b64"]


def test_twin_mutation_requires_auth_and_verified_observation(tmp_path):
    from sara_unified.app import SARAUnified
    client=TestClient(SARAUnified.local(tmp_path/"audit.jsonl").api)
    payload={"entity_id":"svc","state":{"version":"1"},"verified":True,"source":"health"}
    assert client.post("/v1/twin/observe",json=payload).status_code == 401
    ok=client.post("/v1/twin/observe",headers={"Authorization":"Bearer local-operator"},json=payload)
    assert ok.status_code == 200
    assert client.get("/v1/twin").json()["entities"]["svc"]["version"] == "1"
    denied=client.post("/v1/twin/observe",headers={"Authorization":"Bearer local-operator"},json={**payload,"entity_id":"fake","verified":False})
    assert denied.status_code == 422
