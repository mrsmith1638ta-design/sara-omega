from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.ats_intelligence import (
    ATSIntelligenceService,
    ATSStore,
    EmployerRule,
    TailoringRequest,
    VendorChange,
)


def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    return ATSIntelligenceService(ATSStore.from_env())


def test_detects_known_ats_domains(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    assert s.detect("https://acme.wd5.myworkdayjobs.com/en-US/jobs").provider == "workday"
    assert s.detect("https://boards.greenhouse.io/acme/jobs/123").provider == "greenhouse"
    assert s.detect("https://jobs.lever.co/acme/123").provider == "lever"
    assert s.detect("https://acme.taleo.net/careersection/2/jobdetail.ftl").provider == "taleo"


def test_unknown_ats_uses_strict_common_denominator(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    plan = s.tailoring_plan(TailoringRequest(
        employer="Acme", job_title="AI Engineer", application_url="https://jobs.acme.example/apply",
        required_skills=["Python"], candidate_skills=["Python"], candidate_facts=["Built Python services"]
    ))
    assert plan["provider"]["provider"] == "unknown"
    assert "single-column layout" in plan["format_rules"]
    assert any("graphics" in r for r in plan["format_rules"])


def test_workday_required_supported_skill_is_kept_and_gap_is_not_invented(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    plan = s.tailoring_plan(TailoringRequest(
        employer="Acme", job_title="AI Governance Engineer", job_description="governance and IAM",
        application_url="https://acme.myworkdayjobs.com/job/1",
        required_skills=["IAM", "Kubernetes"], preferred_skills=["MFA"],
        candidate_skills=["Identity and Access Management", "Multi-Factor Authentication"],
        candidate_facts=["Implemented identity controls and MFA troubleshooting"]
    ))
    assert "IAM" in plan["supported_required_skills"]
    assert "Kubernetes" in plan["hard_gaps"]
    assert "Kubernetes" not in plan["supported_required_skills"]
    assert plan["resume_lane"] == "AI_GOVERNANCE_CYBERSECURITY"


def test_business_unit_rule_does_not_leak_to_other_unit(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    s.store.save_employer_rule(EmployerRule(
        rule_id="rule-bu-001", employer="Acme", business_unit="Security", scope="business_unit",
        rule_type="required_skill", value="FedRAMP", evidence_url="https://careers.acme.example/security-role",
        observed_at=now, evidence_state="VERIFIED"
    ), "idem-bu-001")
    sec = s.store.applicable_rules("Acme", "Security", None, now=now)
    finance = s.store.applicable_rules("Acme", "Finance", None, now=now)
    assert len(sec) == 1
    assert finance == []


def test_stale_employer_rule_is_suppressed(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    old = datetime.now(timezone.utc) - timedelta(days=20)
    s.store.save_employer_rule(EmployerRule(
        rule_id="rule-old-001", employer="Acme", scope="company", rule_type="remote_rule", value="remote",
        evidence_url="https://careers.acme.example/old", observed_at=old, evidence_state="VERIFIED"
    ), "idem-old-001")
    assert s.store.applicable_rules("Acme", None, None) == []


def test_separate_mutation_authority_rejects_gpt_action_token(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    monkeypatch.setenv("GPT_ACTION_TOKEN", "same-token")
    monkeypatch.setenv("SARA_ATS_INTELLIGENCE_AUTH_TOKEN", "same-token")
    with pytest.raises(HTTPException) as exc:
        s.authorize_mutation("Bearer same-token")
    assert exc.value.status_code == 503


def test_separate_mutation_authority_accepts_distinct_token(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    monkeypatch.setenv("GPT_ACTION_TOKEN", "gpt-token")
    monkeypatch.setenv("SARA_ATS_INTELLIGENCE_AUTH_TOKEN", "ats-token")
    s.authorize_mutation("Bearer ats-token")


def test_idempotency_replay_returns_same_result(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    change = VendorChange(
        event_id="wd-event-001", provider="workday", title="Parsing update", detail="Verified change",
        evidence_url="https://doc.workday.com/example", published_at=now, evidence_state="VERIFIED"
    )
    one = s.store.save_vendor_change(change, "idem-event-001")
    two = s.store.save_vendor_change(change, "idem-event-001")
    assert one == two
    assert s.store.counts()["vendor_events"] == 1


def test_idempotency_key_reuse_with_different_payload_fails(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    one = VendorChange(event_id="event-0001", provider="workday", title="A title", detail="A detail", evidence_url="https://doc.workday.com/a", published_at=now)
    two = VendorChange(event_id="event-0002", provider="workday", title="B title", detail="B detail", evidence_url="https://doc.workday.com/b", published_at=now)
    s.store.save_vendor_change(one, "idem-reuse-001")
    with pytest.raises(ValueError, match="different_payload"):
        s.store.save_vendor_change(two, "idem-reuse-001")


def test_git_attestation_fails_closed_without_commit(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    for name in ("RAILWAY_GIT_COMMIT_SHA", "RAILWAY_GIT_COMMIT", "GIT_COMMIT_SHA", "SOURCE_COMMIT_SHA"):
        monkeypatch.delenv(name, raising=False)
    assert s.health()["git_commit"] == "UNVERIFIED"


def test_invalid_non_https_application_url_is_rejected(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        s.detect("http://example.com/apply")


def test_recent_verified_vendor_change_becomes_bounded_overlay(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    change = VendorChange(
        event_id="wd-overlay-001", provider="workday", title="Candidate profile behavior",
        detail="Official vendor documentation changed candidate matching behavior.",
        evidence_url="https://doc.workday.com/example", published_at=now, observed_at=now,
        evidence_state="VERIFIED", change_type="candidate_profile", resume_impact="ADAPT",
        tailoring_directive="Keep structured candidate-profile data consistent with the submitted resume.",
    )
    s.store.save_vendor_change(change, "idem-overlay-001")
    plan = s.tailoring_plan(TailoringRequest(
        employer="Acme", job_title="AI Engineer", application_url="https://acme.myworkdayjobs.com/job/1",
        candidate_skills=["Python"], candidate_facts=["Built Python services"]
    ))
    assert plan["adaptive_directives"] == ["Keep structured candidate-profile data consistent with the submitted resume."]
    assert plan["current_vendor_changes"][0]["event_id"] == "wd-overlay-001"


def test_unverified_vendor_change_cannot_modify_tailoring(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    change = VendorChange(
        event_id="wd-unverified-001", provider="workday", title="Rumored behavior",
        detail="Unverified third-party claim.", evidence_url="https://example.com/rumor",
        published_at=now, observed_at=now, evidence_state="UNVERIFIED",
        change_type="skills_matching", resume_impact="ADAPT", tailoring_directive="Stuff keywords repeatedly.",
    )
    s.store.save_vendor_change(change, "idem-unverified-001")
    plan = s.tailoring_plan(TailoringRequest(
        employer="Acme", job_title="AI Engineer", application_url="https://acme.myworkdayjobs.com/job/1"
    ))
    assert plan["adaptive_directives"] == []


def test_verified_vendor_change_requires_official_vendor_source(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    change = VendorChange(
        event_id="wd-badsource-001", provider="workday", title="Fake official change", detail="Not official.",
        evidence_url="https://example.com/not-workday", published_at=now, observed_at=now,
        evidence_state="VERIFIED", resume_impact="ADAPT", tailoring_directive="Change everything.",
    )
    with pytest.raises(ValueError, match="verified_vendor_evidence_not_official"):
        s.store.save_vendor_change(change, "idem-badsource-001")
    replay = s.store.save_vendor_change(change, "idem-badsource-001")
    assert replay["status"] == "REJECTED"
    assert replay["automatic_retry"] is False


def test_reserved_idempotency_replay_becomes_submission_unverified(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    payload = {"x": 1}
    fresh, _ = s.store._reserve("idem-unknown-001", "test_op", payload)
    assert fresh
    fresh2, prior = s.store._reserve("idem-unknown-001", "test_op", payload)
    assert not fresh2
    assert prior["status"] == "SUBMISSION_UNVERIFIED"
    assert prior["automatic_retry"] is False


def test_stale_verified_vendor_change_is_suppressed(tmp_path, monkeypatch):
    s = svc(tmp_path, monkeypatch)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    change = VendorChange(
        event_id="wd-stale-001", provider="workday", title="Old behavior", detail="Old verified behavior.",
        evidence_url="https://doc.workday.com/old", published_at=old, observed_at=old,
        evidence_state="VERIFIED", resume_impact="ADAPT", tailoring_directive="Use an old rule.",
    )
    s.store.save_vendor_change(change, "idem-stale-vendor-001")
    plan = s.tailoring_plan(TailoringRequest(
        employer="Acme", job_title="AI Engineer", application_url="https://acme.myworkdayjobs.com/job/1"
    ))
    assert plan["adaptive_directives"] == []


def test_stale_provider_profile_falls_back_to_common_denominator(tmp_path, monkeypatch):
    import app.ats_intelligence as ats
    s = svc(tmp_path, monkeypatch)
    monkeypatch.setattr(ats, "BASELINE_CHECKED_AT", datetime.now(timezone.utc) - timedelta(days=4))
    monkeypatch.setenv("SARA_ATS_PROFILE_MAX_AGE_HOURS", "48")
    plan = s.tailoring_plan(TailoringRequest(
        employer="Acme", job_title="AI Engineer", application_url="https://acme.myworkdayjobs.com/job/1"
    ))
    assert plan["profile_freshness"]["state"] == "STALE_REVALIDATION_REQUIRED"
    assert plan["profile_freshness"]["requires_revalidation"] is True
    assert plan["status"] == "PARTIAL"
    assert "single-column layout" in plan["format_rules"]
    assert not any("Skills field" in rule for rule in plan["format_rules"])


def test_recent_verified_revalidation_refreshes_stale_provider(tmp_path, monkeypatch):
    import app.ats_intelligence as ats
    s = svc(tmp_path, monkeypatch)
    monkeypatch.setattr(ats, "BASELINE_CHECKED_AT", datetime.now(timezone.utc) - timedelta(days=4))
    monkeypatch.setenv("SARA_ATS_PROFILE_MAX_AGE_HOURS", "48")
    now = datetime.now(timezone.utc)
    change = VendorChange(
        event_id="wd-revalidate-001", provider="workday", title="No material resume change",
        detail="Official documentation revalidated.", evidence_url="https://doc.workday.com/revalidated",
        published_at=now, observed_at=now, evidence_state="VERIFIED", resume_impact="NONE"
    )
    s.store.save_vendor_change(change, "idem-revalidate-001")
    fresh = s.profile_freshness("workday")
    assert fresh["state"] == "FRESH"
    assert fresh["requires_revalidation"] is False
