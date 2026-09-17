from pathlib import Path

from fastapi.testclient import TestClient

import main
from app.user_identity import UserIdentityStore
from app.voice_accessibility import VoiceAccessibilityStore


CLIENT_ID = "sara-voice-1-1a-test"
CLIENT_SECRET = "c" * 48
CALLBACK = "https://chat.openai.com/aip/g-voice-test/oauth/callback"
PASSWORD = "Voice-Test-Password-9!Charlie"
OWNER_TOKEN = "o" * 48
ACTION_TOKEN = "a" * 48
TEST_TOKEN = "t" * 48
PREFERENCES = "/v1/accessibility/voice/preferences"
ENTITLEMENTS = "/admin/voice-accessibility/entitlements"

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
