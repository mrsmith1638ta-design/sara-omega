from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.model_sovereignty as model_sovereignty


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MODEL_SOVEREIGNTY_AUTH_TOKEN", "model-authority-token")
    monkeypatch.setenv("OWNER_TOKEN", "owner-token")
    monkeypatch.setenv("GPT_ACTION_TOKEN", "gpt-action-token")
    monkeypatch.setenv("SARA_AUTHORIZED_MODEL_DIGESTS", "sha256:" + "a" * 64)
    monkeypatch.setenv("SOURCE_COMMIT_SHA", "b" * 40)
    model_sovereignty._service_instance = model_sovereignty.ModelSovereigntyService()
    app = FastAPI()
    app.include_router(model_sovereignty.router)
    return TestClient(app)


def test_default_denies_training_authority_for_agent_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    service = model_sovereignty.ModelSovereigntyService()

    verdict = service.evaluate(
        model_sovereignty.ModelLifecycleRequest(
            operation="TRAIN",
            actor="sara-agent-runtime",
            target_model_uri="registry://sara/application-model",
        )
    )

    assert verdict["verdict"] == "DENY"
    assert verdict["reason"] == "BLOCKED_PENDING_MODEL_CHANGE_AUTHORIZATION"
    assert "INV-AI-SELF-01" in verdict["invariants"]
    assert verdict["containment"]["state"] == "CONTAIN_FREEZE_PRESERVE_EVIDENCE_ROLLBACK"


def test_runtime_load_requires_authorized_model_digest(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_AUTHORIZED_MODEL_DIGESTS", "sha256:" + "a" * 64)
    service = model_sovereignty.ModelSovereigntyService()

    verdict = service.evaluate(
        model_sovereignty.ModelLifecycleRequest(
            operation="RUNTIME_LOAD",
            actor="sara-production-runtime",
            target_model_uri="registry://sara/untrusted-model",
            model_digest="sha256:" + "c" * 64,
        )
    )

    assert verdict["verdict"] == "DENY"
    assert verdict["reason"] == "BLOCKED_UNSIGNED_MODEL_ARTIFACT"
    assert verdict["production_load_allowed"] is False


def test_runtime_load_allows_known_digest_without_training_authority(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    digest = "sha256:" + "d" * 64
    monkeypatch.setenv("SARA_AUTHORIZED_MODEL_DIGESTS", digest)
    service = model_sovereignty.ModelSovereigntyService()

    verdict = service.evaluate(
        model_sovereignty.ModelLifecycleRequest(
            operation="RUNTIME_LOAD",
            actor="sara-production-runtime",
            target_model_uri="registry://sara/approved-model",
            model_digest=digest,
        )
    )

    assert verdict["verdict"] == "ALLOW"
    assert verdict["reason"] == "AUTHORIZED_MODEL_DIGEST"
    assert verdict["training_authority"] is False


def test_http_mutation_authority_is_separate_from_owner_and_gpt_tokens(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    payload = {
        "model_digest": "sha256:" + "e" * 64,
        "approval_id": "approval-http-001",
        "approved_by": "external-model-change-authority",
        "scope": "production_runtime_load",
    }

    owner = c.post(
        "/model-sovereignty/authorized-digests",
        json=payload,
        headers={"Authorization": "Bearer owner-token", "Idempotency-Key": "idem-owner-001"},
    )
    gpt = c.post(
        "/model-sovereignty/authorized-digests",
        json=payload,
        headers={"Authorization": "Bearer gpt-action-token", "Idempotency-Key": "idem-gpt-001"},
    )
    separate = c.post(
        "/model-sovereignty/authorized-digests",
        json=payload,
        headers={"Authorization": "Bearer model-authority-token", "Idempotency-Key": "idem-model-001"},
    )

    assert owner.status_code == 403
    assert gpt.status_code == 403
    assert separate.status_code == 200
    assert separate.json()["status"] == "ACCEPTED"


def test_http_evaluate_blocks_untrusted_deploy(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)

    response = c.post(
        "/model-sovereignty/evaluate",
        json={
            "operation": "PROMOTE_MODEL",
            "actor": "sara-agent-runtime",
            "target_model_uri": "registry://sara/model-new-v7",
            "model_digest": "sha256:" + "f" * 64,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "DENY"
    assert body["reason"] == "BLOCKED_UNTRUSTED_MODEL_DIGEST"
