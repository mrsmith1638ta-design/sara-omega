from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from app.voice_accessibility import (
    VoiceAccessRejected,
    VoiceAccessibilityStore,
    VoicePreferences,
)
from app.user_identity import UserIdentityStore


USER_A = "00000000-0000-4000-8000-000000000001"
USER_B = "00000000-0000-4000-8000-000000000002"


def configure_voice_store(monkeypatch, tmp_path):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "51" * 32)


def test_grant_creates_server_owned_individual_tenant(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)

    granted = store.grant_entitlement(USER_A, "owner")
    resolved = store.resolve_access(USER_A)

    assert resolved.tenant_id == granted.tenant_id
    assert resolved.tenant_id != USER_A
    assert resolved.entitlement_status == "ACTIVE"


def test_revocation_is_immediate_and_survives_restart(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    first = VoiceAccessibilityStore.from_env(required=True)
    first.grant_entitlement(USER_A, "owner")
    first.revoke_entitlement(USER_A, "owner")

    second = VoiceAccessibilityStore.from_env(required=True)
    with pytest.raises(VoiceAccessRejected, match="entitlement_inactive"):
        second.resolve_access(USER_A)


def test_expired_entitlement_fails_closed(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
    store.grant_entitlement(USER_A, "owner", expires_at=expiry)

    with pytest.raises(VoiceAccessRejected, match="entitlement_expired"):
        store.resolve_access(USER_A)


def test_preferences_and_jobs_are_user_and_tenant_isolated(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    access_a = store.grant_entitlement(USER_A, "owner")
    access_b = store.grant_entitlement(USER_B, "owner")

    assert store.get_preferences(access_a) == VoicePreferences()
    preferences = VoicePreferences(
        speech_rate="slower",
        preserve_transcript=True,
        transcript_retention_seconds=900,
    )
    assert store.set_preferences(access_a, preferences) == preferences
    assert store.get_preferences(access_b) == VoicePreferences()

    store.record_job("job-a", access_a, "a" * 64, preserve_transcript=False)
    assert store.owns_job("job-a", access_a) is True
    assert store.owns_job("job-a", access_b) is False


def test_transcript_is_encrypted_and_expiry_enforced(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    access = store.grant_entitlement(USER_A, "owner")
    store.record_job("job-a", access, "a" * 64, preserve_transcript=True)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=900)

    store.save_transcript("job-a", access, "Private sentence", expiry)

    assert store.load_transcript("job-a", access) == "Private sentence"
    assert b"Private sentence" not in (tmp_path / "sara_voice_accessibility.db").read_bytes()
    assert store.load_transcript("job-a", access, now=expiry + timedelta(seconds=1)) is None


def test_transcript_requires_job_ownership_and_preservation(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    access_a = store.grant_entitlement(USER_A, "owner")
    access_b = store.grant_entitlement(USER_B, "owner")
    store.record_job("job-a", access_a, "a" * 64, preserve_transcript=False)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=900)

    with pytest.raises(VoiceAccessRejected, match="transcript_preservation_disabled"):
        store.save_transcript("job-a", access_a, "Private sentence", expiry)
    with pytest.raises(VoiceAccessRejected, match="job_not_owned"):
        store.save_transcript("job-a", access_b, "Private sentence", expiry)


def test_purge_removes_preferences_and_transcripts_only(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    access = store.grant_entitlement(USER_A, "owner")
    store.set_preferences(
        access,
        VoicePreferences("faster", True, 900),
    )
    store.record_job("job-a", access, "a" * 64, preserve_transcript=True)
    store.save_transcript(
        "job-a",
        access,
        "Private sentence",
        datetime.now(timezone.utc) + timedelta(seconds=900),
    )

    result = store.purge_user_data(USER_A, "owner")

    assert result == {"preferences_deleted": 1, "transcripts_deleted": 1}
    assert store.get_preferences(access) == VoicePreferences()
    assert store.load_transcript("job-a", access) is None
    assert store.resolve_access(USER_A).entitlement_status == "ACTIVE"


def test_audit_rows_do_not_store_raw_actor_or_target_identifiers(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    store.grant_entitlement(USER_A, "owner-principal")

    with sqlite3.connect(store.db) as conn:
        row = conn.execute(
            "SELECT actor_hash,target_user_hash FROM voice_access_audit ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

    assert row is not None
    assert row[0] != "owner-principal"
    assert row[1] != USER_A


def test_identity_store_can_resolve_account_without_authenticating(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    store = UserIdentityStore.from_env(required=True)
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    account = store.enroll(
        invite_token=invite.token,
        enrollment_id="SARA-NEW-USER",
        password="Correct-Horse-7!Battery",
        password_confirm="Correct-Horse-7!Battery",
    )

    assert store.get_account_by_public_id(account.public_user_id) == account
    assert store.get_account_by_public_id("SARA-U-000000000000") is None
