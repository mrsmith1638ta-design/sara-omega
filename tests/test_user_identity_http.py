from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.user_identity import UserIdentityStore
from app.user_identity_http import router


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "51" * 32)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    monkeypatch.setenv("SARA_PUBLIC_BASE_URL", "https://sara.example")
    monkeypatch.setenv("SARA_GPT_URL", "https://chatgpt.com/g/g-test-sara")
    monkeypatch.setenv("OWNER_TOKEN", "owner-token-unique")
    monkeypatch.setenv("GPT_ACTION_TOKEN", "action-token-unique")
    monkeypatch.setenv("TEST_TOKEN", "test-token-unique")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_ID", "sara-custom-gpt")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_SECRET", "oauth-client-secret-123456789")
    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", "https://chat.openai.com/aip/g-test/oauth/callback")
    monkeypatch.setenv("SARA_OAUTH_SCOPE", "sara.memory sara.solve")


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _create_account(store: UserIdentityStore):
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    account = store.enroll(
        invite_token=invite.token,
        enrollment_id="SARA-NEW-USER",
        password="Correct-Horse-7!Battery",
        password_confirm="Correct-Horse-7!Battery",
    )
    return account


def test_owner_can_create_invitation_but_shared_tokens_cannot(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    client = _client()

    denied_action = client.post(
        "/admin/enrollment/invitations",
        headers={"Authorization": "Bearer action-token-unique"},
    )
    denied_test = client.post(
        "/admin/enrollment/invitations",
        headers={"Authorization": "Bearer test-token-unique"},
    )
    assert denied_action.status_code == 403
    assert denied_test.status_code == 403

    response = client.post(
        "/admin/enrollment/invitations",
        headers={"Authorization": "Bearer owner-token-unique"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["enrollment_id"] == "SARA-NEW-USER"
    assert payload["enrollment_url"].startswith("https://sara.example/enroll/")
    assert "token" not in payload


def test_enrollment_page_has_requested_fields_and_creates_permanent_id(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    client = _client()

    page = client.get(f"/enroll/{invite.token}")
    assert page.status_code == 200
    assert 'name="enrollment_id"' in page.text
    assert 'name="password"' in page.text
    assert 'name="password_confirm"' in page.text
    assert "Create My SARA Account" in page.text

    mismatch = client.post(
        f"/enroll/{invite.token}",
        data={
            "enrollment_id": "SARA-NEW-USER",
            "password": "Correct-Horse-7!Battery",
            "password_confirm": "Correct-Horse-7!Batterx",
        },
    )
    assert mismatch.status_code == 400
    assert "do not match" in mismatch.text.lower()

    success = client.post(
        f"/enroll/{invite.token}",
        data={
            "enrollment_id": "SARA-NEW-USER",
            "password": "Correct-Horse-7!Battery",
            "password_confirm": "Correct-Horse-7!Battery",
        },
    )
    assert success.status_code == 200
    assert "SARA-U-" in success.text
    assert "https://chatgpt.com/g/g-test-sara" in success.text


def test_oauth_authorize_login_redirect_preserves_state(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _create_account(store)
    client = _client()
    params = {
        "client_id": "sara-custom-gpt",
        "redirect_uri": "https://chat.openai.com/aip/g-test/oauth/callback",
        "response_type": "code",
        "scope": "sara.memory sara.solve",
        "state": "opaque-state-123",
    }

    login = client.get("/oauth/authorize", params=params)
    assert login.status_code == 200
    assert 'name="public_user_id"' in login.text
    assert 'name="password"' in login.text
    assert "opaque-state-123" in login.text

    result = client.post(
        "/oauth/authorize",
        data={**params, "public_user_id": account.public_user_id, "password": "Correct-Horse-7!Battery"},
        follow_redirects=False,
    )
    assert result.status_code in {302, 303}
    location = result.headers["location"]
    assert location.startswith("https://chat.openai.com/aip/g-test/oauth/callback?")
    assert "code=" in location
    assert "state=opaque-state-123" in location


def test_oauth_token_exchange_uses_no_store_headers(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _create_account(store)
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id="sara-custom-gpt",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        scope="sara.memory sara.solve",
    )
    client = _client()
    response = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "sara-custom-gpt",
            "client_secret": "oauth-client-secret-123456789",
            "redirect_uri": "https://chat.openai.com/aip/g-test/oauth/callback",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "Bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_oauth_status_never_exposes_secrets(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    response = _client().get("/oauth/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    rendered = response.text
    assert "oauth-client-secret-123456789" not in rendered
    assert "owner-token-unique" not in rendered
