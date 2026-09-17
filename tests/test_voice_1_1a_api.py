from pathlib import Path
from io import BytesIO
import sqlite3
import wave

from fastapi.testclient import TestClient

import main
from app.user_identity import UserIdentityStore
from app.voice_accessibility import VoiceAccessibilityStore, VoiceUsageLimits
import app.voice_accessibility_http as voice_http
from sara_unified.voice.jobs import VoiceJobManager


CLIENT_ID = "sara-voice-1-1a-test"
CLIENT_SECRET = "c" * 48
CALLBACK = "https://chat.openai.com/aip/g-voice-test/oauth/callback"
PASSWORD = "Voice-Test-Password-9!Charlie"
OWNER_TOKEN = "o" * 48
ACTION_TOKEN = "a" * 48
TEST_TOKEN = "t" * 48
PREFERENCES = "/v1/accessibility/voice/preferences"
ENTITLEMENTS = "/admin/voice-accessibility/entitlements"
JOBS = "/v1/accessibility/voice/jobs"

client = TestClient(main.app)


def configure_runtime(monkeypatch, tmp_path: Path, *, enabled=True, public=True):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "61" * 32)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("SARA_OAUTH_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", CALLBACK)
    monkeypatch.setenv(
        "SARA_OAUTH_SCOPE",
        "sara.memory sara.solve sara.voice.accessibility",
    )
    monkeypatch.setenv("SARA_VOICE_1_1_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_1_1A_ENABLED", str(enabled).lower())
    monkeypatch.setenv("SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED", str(public).lower())
    monkeypatch.setenv("OWNER_TOKEN", OWNER_TOKEN)
    monkeypatch.setenv("GPT_ACTION_TOKEN", ACTION_TOKEN)
    monkeypatch.setenv("TEST_TOKEN", TEST_TOKEN)


def provision_account():
    store = UserIdentityStore.from_env(required=True)
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    account = store.enroll(
        invite_token=invite.token,
        enrollment_id="SARA-NEW-USER",
        password=PASSWORD,
        password_confirm=PASSWORD,
    )
    return store, account


def issue_token(store, account, scope):
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id=CLIENT_ID,
        redirect_uri=CALLBACK,
        scope=scope,
    )
    return store.exchange_authorization_code(
        code=code,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
    ).access_token


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def owner_headers():
    return bearer(OWNER_TOKEN)


def wav_bytes():
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 220)
    return output.getvalue()


class FakeVoiceClient:
    def __init__(self):
        self.calls = []
        self.error = None

    def synthesize_with_controls(self, text, controls):
        self.calls.append((text, controls.length_scale))
        if self.error is not None:
            raise self.error
        return wav_bytes()


def install_fake_manager(monkeypatch):
    fake = FakeVoiceClient()
    manager = VoiceJobManager(
        voice_client=fake,
        source_commit_sha="1" * 40,
        deployment_id="voice-1-1a-test-deployment",
        voice_service_url="http://voice.internal:8080",
    )
    monkeypatch.setattr(voice_http, "_voice_job_manager", manager, raising=False)
    return fake


def provision_entitled_voice_user(scope="sara.voice.accessibility"):
    identity, account = provision_account()
    token = issue_token(identity, account, scope)
    VoiceAccessibilityStore.from_env(required=True).grant_entitlement(account.user_uuid, "owner")
    return account, token


def test_each_release_flag_fails_closed(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path, enabled=False, public=True)
    assert client.get(PREFERENCES).status_code == 404

    configure_runtime(monkeypatch, tmp_path, enabled=True, public=False)
    assert client.get(PREFERENCES).status_code == 404


def test_disabled_release_gate_precedes_request_body_validation(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path, enabled=False, public=True)

    response = client.put(PREFERENCES, json={"tenant_id": "forged"})

    assert response.status_code == 404


def test_user_route_requires_oauth_scope_and_entitlement(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    identity, account = provision_account()
    no_voice_scope = issue_token(identity, account, "sara.solve")

    assert client.get(PREFERENCES, headers=bearer(no_voice_scope)).status_code == 403

    voice_token = issue_token(identity, account, "sara.voice.accessibility")
    assert client.get(PREFERENCES, headers=bearer(voice_token)).status_code == 403

    VoiceAccessibilityStore.from_env(required=True).grant_entitlement(account.user_uuid, "owner")
    response = client.get(PREFERENCES, headers=bearer(voice_token))
    assert response.status_code == 200
    assert response.json() == {
        "speech_rate": "normal",
        "preserve_transcript": False,
        "transcript_retention_seconds": 0,
    }


def test_owner_action_and_test_tokens_are_not_oauth_user_credentials(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)

    for token in (OWNER_TOKEN, ACTION_TOKEN, TEST_TOKEN):
        assert client.get(PREFERENCES, headers=bearer(token)).status_code == 401


def test_only_owner_can_grant_read_revoke_and_purge(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    _, account = provision_account()

    denied = client.post(
        ENTITLEMENTS,
        headers=bearer(ACTION_TOKEN),
        json={"public_user_id": account.public_user_id},
    )
    granted = client.post(
        ENTITLEMENTS,
        headers=owner_headers(),
        json={"public_user_id": account.public_user_id},
    )
    status = client.get(
        f"{ENTITLEMENTS}/{account.public_user_id}",
        headers=owner_headers(),
    )
    purged = client.delete(
        f"/admin/voice-accessibility/data/{account.public_user_id}",
        headers=owner_headers(),
    )
    revoked = client.post(
        f"{ENTITLEMENTS}/{account.public_user_id}/revoke",
        headers=owner_headers(),
    )

    assert denied.status_code == 403
    assert granted.status_code == 200
    assert "tenant_id" not in granted.json()
    assert status.status_code == 200
    assert status.json()["status"] == "ACTIVE"
    assert purged.status_code == 200
    assert set(purged.json()) == {"preferences_deleted", "transcripts_deleted"}
    assert revoked.status_code == 200


def test_owner_authorization_precedes_entitlement_body_validation(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)

    response = client.post(
        ENTITLEMENTS,
        headers=bearer(ACTION_TOKEN),
        json={"tenant_id": "forged"},
    )

    assert response.status_code == 403


def test_preferences_are_strict_private_and_no_store(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    identity, account = provision_account()
    token = issue_token(identity, account, "sara.voice.accessibility")
    VoiceAccessibilityStore.from_env(required=True).grant_entitlement(account.user_uuid, "owner")

    forged = client.put(
        PREFERENCES,
        headers=bearer(token),
        json={
            "speech_rate": "normal",
            "preserve_transcript": False,
            "transcript_retention_seconds": 0,
            "tenant_id": "forged",
        },
    )
    updated = client.put(
        PREFERENCES,
        headers=bearer(token),
        json={
            "speech_rate": "slower",
            "preserve_transcript": True,
            "transcript_retention_seconds": 900,
        },
    )

    assert forged.status_code == 422
    assert updated.status_code == 200
    assert updated.json()["speech_rate"] == "slower"
    assert updated.headers["cache-control"] == "private, no-store"


def test_revocation_blocks_preferences_immediately(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    identity, account = provision_account()
    token = issue_token(identity, account, "sara.voice.accessibility")
    store = VoiceAccessibilityStore.from_env(required=True)
    store.grant_entitlement(account.user_uuid, "owner")
    assert client.get(PREFERENCES, headers=bearer(token)).status_code == 200

    store.revoke_entitlement(account.user_uuid, "owner")

    assert client.get(PREFERENCES, headers=bearer(token)).status_code == 403


def test_entitled_user_can_speak_and_fetch_private_audio(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    fake = install_fake_manager(monkeypatch)
    _, token = provision_entitled_voice_user()

    created = client.post(
        JOBS,
        headers=bearer(token),
        json={"text": "First. Second.", "speech_rate": "faster"},
    )

    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "completed"
    assert len(body["segments"]) == 2
    assert len(fake.calls) == 2
    job_id = body["job_id"]
    segment_id = body["segments"][0]["segment_id"]
    audio = client.get(
        f"{JOBS}/{job_id}/segments/{segment_id}/audio",
        headers=bearer(token),
    )
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/wav")
    assert audio.headers["cache-control"] == "private, no-store"
    assert audio.content == wav_bytes()


def test_cross_tenant_job_surfaces_are_hidden(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    install_fake_manager(monkeypatch)
    _, token_a = provision_entitled_voice_user()
    _, token_b = provision_entitled_voice_user()
    created = client.post(
        JOBS,
        headers=bearer(token_a),
        json={"text": "Private sentence.", "preserve_transcript": True},
    )
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    segment_id = created.json()["segments"][0]["segment_id"]

    get_paths = (
        f"{JOBS}/{job_id}",
        f"{JOBS}/{job_id}/receipts",
        f"{JOBS}/{job_id}/transcript",
        f"{JOBS}/{job_id}/segments/{segment_id}/audio",
    )
    assert all(client.get(path, headers=bearer(token_b)).status_code == 404 for path in get_paths)
    assert client.post(f"{JOBS}/{job_id}/stop", headers=bearer(token_b)).status_code == 404


def test_transcript_and_receipts_are_private_and_ownership_bound(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    install_fake_manager(monkeypatch)
    _, token = provision_entitled_voice_user()
    created = client.post(
        JOBS,
        headers=bearer(token),
        json={"text": "Preserve this transcript.", "preserve_transcript": True},
    )
    job_id = created.json()["job_id"]

    transcript = client.get(f"{JOBS}/{job_id}/transcript", headers=bearer(token))
    receipts = client.get(f"{JOBS}/{job_id}/receipts", headers=bearer(token))

    assert transcript.status_code == 200
    assert transcript.json() == {"transcript": "Preserve this transcript."}
    assert transcript.headers["cache-control"] == "private, no-store"
    assert receipts.status_code == 200
    assert receipts.headers["cache-control"] == "private, no-store"
    assert receipts.json()["access_envelope_sha256"]
    assert "user_uuid" not in receipts.text
    assert "tenant_id" not in receipts.text


def test_stop_is_idempotent_for_owned_job(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    install_fake_manager(monkeypatch)
    _, token = provision_entitled_voice_user()
    created = client.post(JOBS, headers=bearer(token), json={"text": "One. Two."})
    job_id = created.json()["job_id"]

    first = client.post(f"{JOBS}/{job_id}/stop", headers=bearer(token))
    second = client.post(f"{JOBS}/{job_id}/stop", headers=bearer(token))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["stop_requested_at"] == second.json()["stop_requested_at"]


def test_piper_failure_releases_lease_but_keeps_usage(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    fake = install_fake_manager(monkeypatch)
    fake.error = RuntimeError("private renderer detail")
    _, token = provision_entitled_voice_user()

    failed = client.post(JOBS, headers=bearer(token), json={"text": "Fail safely."})

    assert failed.status_code == 502
    assert "private renderer detail" not in failed.text
    db = tmp_path / "sara_voice_accessibility.db"
    with sqlite3.connect(db) as conn:
        leases = conn.execute("SELECT COUNT(*) FROM voice_leases").fetchone()[0]
        minute_usage = conn.execute(
            "SELECT SUM(job_count) FROM voice_usage_windows WHERE subject_kind='USER' AND window_kind='MINUTE'"
        ).fetchone()[0]
    assert leases == 0
    assert minute_usage == 1


def test_user_quota_returns_bounded_429_and_retry_after(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("SARA_VOICE_1_1A_USER_JOBS_PER_MINUTE", "1")
    install_fake_manager(monkeypatch)
    _, token = provision_entitled_voice_user()
    assert client.post(JOBS, headers=bearer(token), json={"text": "First."}).status_code == 200

    limited = client.post(JOBS, headers=bearer(token), json={"text": "Second."})

    assert limited.status_code == 429
    assert limited.json()["detail"] == "user_jobs_per_minute"
    assert int(limited.headers["retry-after"]) > 0


def test_concurrency_limit_returns_bounded_409(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    install_fake_manager(monkeypatch)
    account, token = provision_entitled_voice_user()
    store = VoiceAccessibilityStore.from_env(required=True)
    access = store.resolve_access(account.user_uuid)
    settings = voice_http.Settings.from_env()
    store.reserve_usage(
        access,
        characters=1,
        limits=VoiceUsageLimits(
            user_jobs_per_minute=settings.voice_1_1a_user_jobs_per_minute,
            user_jobs_per_day=settings.voice_1_1a_user_jobs_per_day,
            user_characters_per_day=settings.voice_1_1a_user_characters_per_day,
            tenant_jobs_per_minute=settings.voice_1_1a_tenant_jobs_per_minute,
            tenant_jobs_per_day=settings.voice_1_1a_tenant_jobs_per_day,
            tenant_characters_per_day=settings.voice_1_1a_tenant_characters_per_day,
            user_concurrency=settings.voice_1_1a_user_concurrency,
            tenant_concurrency=settings.voice_1_1a_tenant_concurrency,
            lease_seconds=settings.voice_1_1a_lease_seconds,
        ),
    )

    response = client.post(JOBS, headers=bearer(token), json={"text": "Blocked."})

    assert response.status_code == 409
    assert response.json()["detail"] == "user_concurrency"


def test_disabled_job_gate_precedes_strict_body_validation(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path, enabled=False, public=True)

    response = client.post(JOBS, json={"tenant_id": "forged"})

    assert response.status_code == 404


def test_revoked_entitlement_blocks_every_existing_job_route(monkeypatch, tmp_path):
    configure_runtime(monkeypatch, tmp_path)
    install_fake_manager(monkeypatch)
    account, token = provision_entitled_voice_user()
    created = client.post(
        JOBS,
        headers=bearer(token),
        json={"text": "Revoke this access.", "preserve_transcript": True},
    )
    job_id = created.json()["job_id"]
    segment_id = created.json()["segments"][0]["segment_id"]
    VoiceAccessibilityStore.from_env(required=True).revoke_entitlement(account.user_uuid, "owner")

    get_paths = (
        f"{JOBS}/{job_id}",
        f"{JOBS}/{job_id}/receipts",
        f"{JOBS}/{job_id}/transcript",
        f"{JOBS}/{job_id}/segments/{segment_id}/audio",
    )
    assert all(client.get(path, headers=bearer(token)).status_code == 403 for path in get_paths)
    assert client.post(f"{JOBS}/{job_id}/stop", headers=bearer(token)).status_code == 403
