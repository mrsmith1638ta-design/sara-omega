import json
from dataclasses import replace

from fastapi.testclient import TestClient

from sara_unified.app import SARAUnified
from sara_unified.config import Settings
from sara_unified.evidence.audit import AuditLedger
from sara_unified.operations.recovery import RecoveryAction


AUTH = {"Authorization": "Bearer local-operator"}


def _twin_payload(entity_id="svc-a"):
    return {
        "entity_id": entity_id,
        "state": {"version": "1"},
        "verified": True,
        "source": "health",
    }


def test_mutation_receives_governance_evidence_before_side_effect(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    app = SARAUnified.local(audit_path=audit_path)
    client = TestClient(app.api)

    response = client.post("/v1/twin/observe", json=_twin_payload(), headers=AUTH)

    assert response.status_code == 200
    evidence_hash = response.json()["governance_evidence_hash"]
    assert len(evidence_hash) == 64
    assert app.twin.get("svc-a") is not None

    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records[-2]["action"] == "GOVERNANCE_AUTHORIZATION"
    assert (
        records[-2]["details"]["execution_evidence"]["evidence_hash"]
        == evidence_hash
    )
    assert records[-2]["details"]["execution_evidence"]["decision"] == "ALLOW"
    assert records[-1]["action"] == "TWIN_OBSERVED"
    assert records[-1]["details"]["governance_evidence_hash"] == evidence_hash


def test_production_missing_signing_key_fails_closed_before_mutation(tmp_path):
    settings = Settings(
        governance_enforcement_required=True,
        governance_signing_key="",
    )
    app = SARAUnified(
        AuditLedger(tmp_path / "audit.jsonl"),
        settings=settings,
        allow_local_operator=True,
    )
    client = TestClient(app.api)

    response = client.post("/v1/twin/observe", json=_twin_payload(), headers=AUTH)

    assert response.status_code == 503
    assert app.twin.get("svc-a") is None
    assert response.json()["detail"]["error"] == "governance_execution_blocked"


def test_invalid_audit_chain_fails_closed_before_mutation(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    app = SARAUnified.local(audit_path=audit_path)
    client = TestClient(app.api)

    app.audit.append("test", "SEED", {"value": 1})
    text = audit_path.read_text(encoding="utf-8")
    audit_path.write_text(text.replace('"value":1', '"value":9'), encoding="utf-8")
    assert app.audit.verify() is False

    response = client.post(
        "/v1/twin/observe",
        json=_twin_payload("svc-tamper"),
        headers=AUTH,
    )

    assert response.status_code == 503
    assert app.twin.get("svc-tamper") is None


def test_policy_denial_blocks_executor_and_preserves_state(tmp_path):
    app = SARAUnified.local(audit_path=tmp_path / "audit.jsonl")
    app.governance.policy = replace(
        app.governance.policy,
        allowed_actions=tuple(
            action
            for action in app.governance.policy.allowed_actions
            if action != "twin.observe"
        ),
    )
    client = TestClient(app.api)

    response = client.post(
        "/v1/twin/observe",
        json=_twin_payload("svc-denied"),
        headers=AUTH,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["decision"] == "DENY"
    assert app.twin.get("svc-denied") is None


def test_recovery_without_human_approval_escalates_before_executor(tmp_path):
    app = SARAUnified.local(audit_path=tmp_path / "audit.jsonl")
    called = []
    app.recovery._actions["restart"] = RecoveryAction(
        "restart",
        True,
        lambda ctx: called.append(ctx) or {"ok": True},
    )
    client = TestClient(app.api)

    response = client.post(
        "/v1/recovery/restart",
        json={"context": {"service": "payments"}, "approved": False},
        headers=AUTH,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["decision"] == "ESCALATE"
    assert called == []


def test_approved_recovery_executes_with_evidence_hash(tmp_path):
    app = SARAUnified.local(audit_path=tmp_path / "audit.jsonl")
    called = []
    app.recovery._actions["restart"] = RecoveryAction(
        "restart",
        True,
        lambda ctx: called.append(ctx) or {"ok": True},
    )
    client = TestClient(app.api)

    response = client.post(
        "/v1/recovery/restart",
        json={"context": {"service": "payments"}, "approved": True},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert called == [{"service": "payments"}]
    assert len(response.json()["governance_evidence_hash"]) == 64


def test_incident_creation_crosses_governance_boundary(tmp_path):
    app = SARAUnified.local(audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app.api)

    response = client.post(
        "/v1/incidents",
        json={"title": "database latency", "severity": "HIGH", "affected": ["db-a"]},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert len(response.json()["governance_evidence_hash"]) == 64


class _VoiceClient:
    def __init__(self):
        self.calls = []

    def synthesize(self, text):
        self.calls.append(text)
        return b"RIFFtest"


def test_voice_side_effect_crosses_governance_boundary(tmp_path):
    voice = _VoiceClient()
    settings = Settings(voice_enabled=True)
    app = SARAUnified(
        AuditLedger(tmp_path / "audit.jsonl"),
        settings=settings,
        allow_local_operator=True,
        voice_client=voice,
    )
    client = TestClient(app.api)

    response = client.post(
        "/v1/voice/synthesize",
        json={"text": "governed speech"},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert voice.calls == ["governed speech"]
    assert len(response.headers["X-SARA-Governance-Evidence"]) == 64
