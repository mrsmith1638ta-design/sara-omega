import copy
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient


def test_audit_chain_detects_tampering(tmp_path):
    from sara_unified.evidence.audit import AuditLedger
    ledger = AuditLedger(tmp_path / "audit.jsonl")
    first = ledger.append("actor", "CREATE", {"x": 1})
    second = ledger.append("actor", "UPDATE", {"x": 2})
    assert first.event_hash != second.event_hash
    assert ledger.verify() is True
    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    (tmp_path / "audit.jsonl").write_text(lines[0].replace('"x":1', '"x":9') + "\n" + lines[1] + "\n")
    assert ledger.verify() is False


def test_authorization_is_default_deny():
    from sara_unified.security.authorization import Authorizer
    authz = Authorizer({"admin": {"twin:read"}})
    assert authz.allowed({"admin"}, "twin:read")
    assert not authz.allowed({"admin"}, "recovery:execute")
    assert not authz.allowed(set(), "twin:read")


def test_replay_guard_rejects_reuse_and_stale_timestamp():
    from sara_unified.security.replay import ReplayGuard
    guard = ReplayGuard(max_age_seconds=30)
    now = int(time.time())
    guard.check("nonce-1", now)
    with pytest.raises(Exception):
        guard.check("nonce-1", now)
    with pytest.raises(Exception):
        guard.check("nonce-2", now - 31)


def test_evidence_fusion_preserves_contradiction():
    from sara_unified.evidence.claims import Claim, EpistemicStatus
    from sara_unified.evidence.fusion import EvidenceFusion
    a = Claim.create("service is healthy", "source-a", EpistemicStatus.VERIFIED, polarity=1)
    b = Claim.create("service is healthy", "source-b", EpistemicStatus.VERIFIED, polarity=-1)
    result = EvidenceFusion().fuse([a, b])
    assert result.status is EpistemicStatus.DISPUTED
    assert set(result.contradiction_claim_ids) == {a.claim_id, b.claim_id}


def test_passport_signature_detects_tampering():
    from sara_unified.evidence.passports import CapabilityPassport
    from sara_unified.evidence.signing import Ed25519Signer
    signer = Ed25519Signer.generate()
    passport = CapabilityPassport.create("jury", "1.0.0", ["evidence"], ["jury:run"])
    signed = signer.sign_json(passport.payload())
    assert signer.verify_json(passport.payload(), signed.signature_b64)
    tampered = dict(passport.payload()); tampered["version"] = "9.9.9"
    assert not signer.verify_json(tampered, signed.signature_b64)


def test_jury_does_not_use_majority_alone():
    from sara_unified.cognition.jury import JuryOpinion, ModelJury
    opinions = [
        JuryOpinion("m1", "A", 0.5, ["same-source"]),
        JuryOpinion("m2", "A", 0.5, ["same-source"]),
        JuryOpinion("m3", "B", 0.95, ["independent-1", "independent-2"]),
    ]
    result = ModelJury().deliberate(opinions)
    assert result.resolution == "UNRESOLVED"
    assert result.disagreements


def test_counterfactual_isolation():
    from sara_unified.cognition.counterfactual import CounterfactualEngine
    baseline = {"service": {"replicas": 2}}
    original = copy.deepcopy(baseline)
    result = CounterfactualEngine().simulate(baseline, {"service.replicas": 3})
    assert baseline == original
    assert result.simulated_state["service"]["replicas"] == 3


def test_digital_twin_requires_verified_observation():
    from sara_unified.operations.digital_twin import DigitalTwin
    twin = DigitalTwin()
    twin.observe("svc-a", {"version": "1"}, verified=False, source="config")
    assert twin.get("svc-a") is None
    twin.observe("svc-a", {"version": "1"}, verified=True, source="health")
    assert twin.get("svc-a").state["version"] == "1"


def test_recovery_requires_approval_when_declared():
    from sara_unified.operations.recovery import RecoveryRegistry, RecoveryAction
    called = []
    reg = RecoveryRegistry()
    reg.register(RecoveryAction("restart", requires_approval=True, executor=lambda ctx: called.append(ctx) or {"ok": True}))
    denied = reg.execute("restart", {"service": "x"}, approved=False)
    assert denied.executed is False
    assert called == []
    ok = reg.execute("restart", {"service": "x"}, approved=True)
    assert ok.executed is True and called


def test_readiness_fails_closed_when_mandatory_dependency_untrusted():
    from sara_unified.operations.observability import HealthAggregator
    h = HealthAggregator()
    h.set_dependency("road", reachable=True, trusted=False, mandatory=True)
    assert h.ready() is False
    h.set_dependency("road", reachable=True, trusted=True, mandatory=True)
    assert h.ready() is True


def test_skill_activation_requires_policy_authorization():
    from sara_unified.skills.compiler import SkillCompiler, WorkflowStep
    from sara_unified.skills.registry import SkillRegistry
    compiled = SkillCompiler().compile("safe", [WorkflowStep("read", "twin:read", external_effect=False, rollback=None)])
    registry = SkillRegistry()
    registry.register(compiled)
    assert registry.activate("safe", policy_authorized=False) is False
    assert registry.activate("safe", policy_authorized=True) is True


def test_api_rejects_unauthorized_state_change(tmp_path):
    from sara_unified.app import SARAUnified
    app = SARAUnified.local(audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app.api)
    assert client.get("/health").status_code == 200
    assert client.get("/readyz").status_code in (200, 503)
    r = client.post("/v1/recovery/restart", json={"context": {"service": "x"}})
    assert r.status_code == 401
