from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.ats_intelligence as ats


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_ATS_INTELLIGENCE_AUTH_TOKEN", "ats-http-token")
    monkeypatch.setenv("GPT_ACTION_TOKEN", "gpt-http-token")
    monkeypatch.setenv("SOURCE_COMMIT_SHA", "a" * 40)
    ats._service_instance = ats.ATSIntelligenceService(ats.ATSStore.from_env())
    app = FastAPI()
    app.include_router(ats.router)
    return TestClient(app)


def test_http_health_and_exact_commit_attestation(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    health = c.get("/ats-intelligence/health")
    assert health.status_code == 200
    body = health.json()
    assert body["mutation_authority_separate"] is True
    assert body["dynamic_vendor_overlays"] is True
    att = c.get("/ats-intelligence/attestation").json()
    assert att["git_commit"] == "a" * 40
    assert att["execution_authority"] is False


def test_http_mutation_rejects_missing_auth(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    payload = {
        "event_id": "wd-http-001", "provider": "workday", "title": "Official update",
        "detail": "Official update detail", "evidence_url": "https://doc.workday.com/http",
        "published_at": datetime.now(timezone.utc).isoformat(), "evidence_state": "VERIFIED",
    }
    r = c.post("/ats-intelligence/vendor-change", json=payload, headers={"Idempotency-Key": "idem-http-001"})
    assert r.status_code == 403


def test_http_verified_vendor_overlay_flow(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "event_id": "wd-http-002", "provider": "workday", "title": "Official profile update",
        "detail": "Verified official behavior", "evidence_url": "https://doc.workday.com/http-two",
        "published_at": now, "observed_at": now, "evidence_state": "VERIFIED",
        "change_type": "candidate_profile", "resume_impact": "ADAPT",
        "tailoring_directive": "Keep verified structured profile fields aligned with the resume.",
    }
    r = c.post(
        "/ats-intelligence/vendor-change", json=payload,
        headers={"Authorization": "Bearer ats-http-token", "Idempotency-Key": "idem-http-002"},
    )
    assert r.status_code == 200
    plan = c.post("/ats-intelligence/tailor-plan", json={
        "employer": "Acme", "job_title": "AI Governance Engineer",
        "application_url": "https://acme.myworkdayjobs.com/job/2",
        "required_skills": ["IAM"], "candidate_skills": ["Identity and Access Management"],
    })
    assert plan.status_code == 200
    body = plan.json()
    assert body["adaptive_directives"] == ["Keep verified structured profile fields aligned with the resume."]
    assert body["supported_required_skills"] == ["IAM"]


def test_http_non_https_application_url_rejected_at_validation(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/ats-intelligence/detect", json={"application_url": "http://example.com/apply"})
    assert r.status_code == 422


def test_http_oversized_skill_item_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/ats-intelligence/tailor-plan", json={
        "employer": "Acme", "job_title": "AI Engineer",
        "application_url": "https://jobs.acme.example/apply",
        "required_skills": ["x" * 301],
    })
    assert r.status_code == 422
