import json
import time
import pytest
from fastapi.testclient import TestClient


def test_mandatory_road_fails_closed_without_provider():
    from sara_unified.governance.road import RoadGate
    from sara_unified.errors import GovernanceUnavailableError
    with pytest.raises(GovernanceUnavailableError):
        RoadGate(mandatory=True).status()


def test_mandatory_sios_fails_closed_without_provider():
    from sara_unified.governance.sios import SIOSGate
    from sara_unified.errors import GovernanceUnavailableError
    with pytest.raises(GovernanceUnavailableError):
        SIOSGate(mandatory=True).authorize({"action": "restart"})


def test_authority_chain_requires_approval_for_state_change():
    from sara_unified.contracts import RequestContext, OperationClass
    from sara_unified.security.authorization import Authorizer
    from sara_unified.governance.policy import PolicyEngine
    from sara_unified.governance.approvals import ApprovalStore
    from sara_unified.governance.authority import AuthorityChain
    approvals = ApprovalStore()
    chain = AuthorityChain(Authorizer({"admin": {"service:change"}}), PolicyEngine(), approvals)
    ctx = RequestContext("alice", frozenset({"admin"}))
    assert not chain.decide(ctx, "service:change", OperationClass.STATE_CHANGING, "restart:svc").allowed
    approvals.grant("alice", "owner", "restart:svc")
    assert chain.decide(ctx, "service:change", OperationClass.STATE_CHANGING, "restart:svc").allowed


def test_rate_limiter_blocks_excess_requests():
    from sara_unified.security.rate_limit import TokenBucketRateLimiter
    limiter = TokenBucketRateLimiter(capacity=2, refill_per_second=0)
    assert limiter.allow("actor")
    assert limiter.allow("actor")
    assert not limiter.allow("actor")


def test_write_freeze_blocks_mutation():
    from sara_unified.security.state import SecurityState
    state = SecurityState()
    assert state.can_write("tenant-a")
    state.freeze_writes("tenant-a", "incident")
    assert not state.can_write("tenant-a")
    state.unfreeze_writes("tenant-a")
    assert state.can_write("tenant-a")


def test_sqlalchemy_persistence_round_trip(tmp_path):
    from sara_unified.persistence.db import create_database, PersistedEvent
    engine, Session = create_database(f"sqlite+pysqlite:///{tmp_path/'db.sqlite'}")
    with Session.begin() as s:
        s.add(PersistedEvent(event_hash="a"*64, payload='{"ok":true}'))
    with Session() as s:
        row = s.query(PersistedEvent).filter_by(event_hash="a"*64).one()
        assert json.loads(row.payload)["ok"] is True
    engine.dispose()


def test_incident_commander_tracks_containment_and_blast_radius():
    from sara_unified.operations.digital_twin import DigitalTwin
    from sara_unified.operations.incidents import IncidentCommander
    cmd = IncidentCommander(DigitalTwin())
    incident = cmd.create("provider failure", "HIGH", affected=["api", "model"])
    assert cmd.blast_radius(incident.incident_id) == ("api", "model")
    cmd.contain(incident.incident_id, "circuit opened")
    assert incident.containment_state == "CONTAINED"
    assert incident.timeline[-1]["event"] == "contained"


def test_gap_radar_flags_disputed_claim_and_undocumented_dependency():
    from sara_unified.evidence.claims import Claim, EpistemicStatus
    from sara_unified.cognition.gaps import KnowledgeGapRadar
    claim = Claim.create("x", "a", EpistemicStatus.DISPUTED)
    gaps = KnowledgeGapRadar().derive([claim], [{"name":"redis", "documented":False}])
    assert {g.category for g in gaps} == {"evidence", "dependency"}


def test_api_exposes_twin_evidence_incident_and_jury_routes(tmp_path):
    from sara_unified.app import SARAUnified
    client = TestClient(SARAUnified.local(tmp_path/"audit.jsonl").api)
    assert client.get("/v1/twin").status_code == 200
    assert client.get("/v1/evidence/audit-status").json()["valid"] is True
    jury = client.post("/v1/jury/deliberate", json={"opinions":[
        {"model_id":"a","conclusion":"X","confidence":0.8,"evidence_refs":["1"]},
        {"model_id":"b","conclusion":"Y","confidence":0.8,"evidence_refs":["2"]}
    ]})
    assert jury.status_code == 200 and jury.json()["resolution"] == "UNRESOLVED"
    inc = client.post("/v1/incidents", headers={"Authorization":"Bearer local-operator"}, json={"title":"x","severity":"HIGH","affected":["api"]})
    assert inc.status_code == 200


def test_api_recovery_requires_explicit_approval_even_when_authenticated(tmp_path):
    from sara_unified.app import SARAUnified
    client = TestClient(SARAUnified.local(tmp_path/"audit.jsonl").api)
    h={"Authorization":"Bearer local-operator"}
    denied=client.post("/v1/recovery/restart",headers=h,json={"context":{"service":"x"},"approved":False})
    assert denied.status_code == 403
    ok=client.post("/v1/recovery/restart",headers=h,json={"context":{"service":"x"},"approved":True})
    assert ok.status_code == 200 and ok.json()["executed"] is True
