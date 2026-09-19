from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.enterprise_governance as governance


def _now() -> datetime:
    return datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)


def _feature(**overrides):
    data = {
        "record_id": "feat-openai-gpt-action-ent-001",
        "tenant_id": "tenant-a",
        "provider_id": "openai",
        "product": "ChatGPT Enterprise",
        "plan": "Enterprise",
        "feature": "GPT Action",
        "region": "us",
        "required_configuration": {"oauth": True, "approved_domain": True},
        "evidence_refs": ["artifact-openai-action-scope-001"],
        "evidence_state": "PASS",
        "operational_status": "ELIGIBLE",
        "effective_from": _now().isoformat(),
        "expires_at": (_now() + timedelta(days=30)).isoformat(),
        "exclusions": [],
    }
    data.update(overrides)
    return governance.FeatureEligibilityRecord(**data)


def _inheritance(**overrides):
    data = {
        "record_id": "ctrl-openai-action-auth-001",
        "tenant_id": "tenant-a",
        "control_id": "AUTH-SSO-RBAC",
        "provider_id": "openai",
        "product": "ChatGPT Enterprise",
        "plan": "Enterprise",
        "feature": "GPT Action",
        "owner": "SHARED",
        "disposition": "SHARED",
        "evidence_refs": ["artifact-openai-action-scope-001"],
        "evidence_state": "PASS",
        "exclusions": [],
        "reviewed_at": _now().isoformat(),
        "next_review_at": (_now() + timedelta(days=30)).isoformat(),
    }
    data.update(overrides)
    return governance.ControlInheritanceRecord(**data)


def _request(**overrides):
    data = {
        "tenant_id": "tenant-a",
        "actor_id": "user-1",
        "provider_id": "openai",
        "product": "ChatGPT Enterprise",
        "plan": "Enterprise",
        "feature": "GPT Action",
        "region": "us",
        "requested_action": "governance_evaluate_action",
        "actor_scopes": ["sara.governance.evaluate"],
        "configuration": {"oauth": True, "approved_domain": True},
    }
    data.update(overrides)
    return governance.GovernanceEvaluationRequest(**data)


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_ENTERPRISE_GOVERNANCE_ADMIN_TOKEN", "governance-admin-token")
    monkeypatch.setenv("OWNER_TOKEN", "owner-token")
    monkeypatch.setenv("GPT_ACTION_TOKEN", "gpt-action-token")
    monkeypatch.setenv("SOURCE_COMMIT_SHA", "c" * 40)
    governance._service_instance = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.from_env()
    )
    app = FastAPI()
    app.include_router(governance.router)
    return TestClient(app)


def test_missing_feature_record_blocks():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )

    decision = service.evaluate(_request(), now=_now())

    assert decision["decision"] == "DENY"
    assert "FEATURE_NOT_REGISTERED" in decision["reasons"]
    assert decision["evidence_state"] == "UNVERIFIED"


def test_partial_or_unverified_evidence_never_becomes_pass():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )
    service.store.upsert_feature(_feature(evidence_state="PARTIAL"))
    service.store.upsert_control(_inheritance())

    decision = service.evaluate(_request(), now=_now())

    assert decision["decision"] == "DENY"
    assert decision["evidence_state"] == "PARTIAL"
    assert "FEATURE_EVIDENCE_NOT_PASS" in decision["reasons"]


def test_expired_assurance_blocks_inheritance():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )
    service.store.upsert_feature(_feature(expires_at=(_now() - timedelta(seconds=1)).isoformat()))
    service.store.upsert_control(_inheritance())

    decision = service.evaluate(_request(), now=_now())

    assert decision["decision"] == "DENY"
    assert "FEATURE_EVIDENCE_STALE" in decision["reasons"]


def test_provider_identity_does_not_imply_scope_or_plan():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )
    service.store.upsert_feature(_feature(plan="Enterprise"))
    service.store.upsert_control(_inheritance(plan="Enterprise"))

    decision = service.evaluate(_request(plan="Business"), now=_now())

    assert decision["decision"] == "DENY"
    assert "FEATURE_NOT_REGISTERED" in decision["reasons"]


def test_feature_exclusion_and_missing_scope_block():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )
    service.store.upsert_feature(_feature(exclusions=["conversation-message ingestion"]))
    service.store.upsert_control(_inheritance())

    excluded = service.evaluate(
        _request(requested_action="conversation-message ingestion", actor_scopes=["sara.governance.evaluate"]),
        now=_now(),
    )
    missing_scope = service.evaluate(_request(actor_scopes=["sara.solve"]), now=_now())

    assert excluded["decision"] == "DENY"
    assert "FEATURE_EXCLUSION_APPLIES" in excluded["reasons"]
    assert missing_scope["decision"] == "DENY"
    assert "INSUFFICIENT_SCOPE" in missing_scope["reasons"]


def test_human_approval_cannot_be_self_granted():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )
    service.store.upsert_feature(_feature())
    service.store.upsert_control(_inheritance())

    decision = service.evaluate(
        _request(
            requested_action="governance_create_audit_passport",
            actor_scopes=["sara.governance.evaluate", "sara.governance.admin"],
            human_approval_id=None,
        ),
        now=_now(),
    )

    assert decision["decision"] == "REQUIRE_APPROVAL"
    assert "HUMAN_APPROVAL_REQUIRED" in decision["reasons"]


def test_passport_never_claims_independent_audit_or_leaks_secrets():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )
    service.store.upsert_feature(_feature())
    service.store.upsert_control(_inheritance())
    decision = service.evaluate(_request(), now=_now())

    passport = service.create_audit_passport(
        tenant_id="tenant-a",
        release_identity="SARA-OMEGA 3.4.0-candidate",
        source_commit="abc1234",
        decision_ids=[decision["decision_id"]],
        notes="server secret sk-test OWNER_TOKEN=abc admin key should be redacted",
        now=_now(),
    )

    assert passport["independent_assurance"] is False
    assert passport["audit_opinion"] is False
    assert passport["certification_statement"] is False
    assert "sk-test" not in str(passport)
    assert "OWNER_TOKEN" not in str(passport)
    assert "admin key" not in str(passport).lower()


def test_cross_tenant_passport_access_blocks():
    service = governance.EnterpriseGovernanceService(
        governance.EnterpriseGovernanceStore.in_memory()
    )
    passport = service.create_audit_passport(
        tenant_id="tenant-a",
        release_identity="candidate",
        source_commit="abc1234",
        decision_ids=[],
        notes="",
        now=_now(),
    )

    assert service.get_audit_passport(passport["passport_id"], tenant_id="tenant-b") is None


def test_http_admin_mutation_rejects_owner_and_gpt_tokens(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    payload = _feature().model_dump(mode="json")

    owner = c.post(
        "/enterprise-governance/feature-eligibility",
        json=payload,
        headers={"Authorization": "Bearer owner-token", "Idempotency-Key": "idem-owner-001"},
    )
    gpt = c.post(
        "/enterprise-governance/feature-eligibility",
        json=payload,
        headers={"Authorization": "Bearer gpt-action-token", "Idempotency-Key": "idem-gpt-001"},
    )
    admin = c.post(
        "/enterprise-governance/feature-eligibility",
        json=payload,
        headers={"Authorization": "Bearer governance-admin-token", "Idempotency-Key": "idem-admin-001"},
    )

    assert owner.status_code == 403
    assert gpt.status_code == 403
    assert admin.status_code == 200
    assert admin.json()["status"] == "ACCEPTED"


def test_http_evaluate_records_governed_decision(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer governance-admin-token"}
    c.post(
        "/enterprise-governance/feature-eligibility",
        json=_feature().model_dump(mode="json"),
        headers={**headers, "Idempotency-Key": "idem-feature-001"},
    )
    c.post(
        "/enterprise-governance/control-inheritance",
        json=_inheritance().model_dump(mode="json"),
        headers={**headers, "Idempotency-Key": "idem-control-001"},
    )

    response = c.post("/enterprise-governance/evaluate-action", json=_request().model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["reasons"] == ["GOVERNED_EXECUTION_ALLOWED"]
    assert body["independent_assurance"] is False
