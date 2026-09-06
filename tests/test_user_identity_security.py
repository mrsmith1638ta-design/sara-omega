from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.user_identity import UserIdentityStore
from app.user_identity_http import router as identity_router


CLIENT_ID = "sara-schema-security-test"
CLIENT_SECRET = "q" * 48
CALLBACK = "https://chat.openai.com/aip/g-security/oauth/callback"
OWNER_TOKEN = "o" * 48
ACTION_TOKEN = "a" * 48
TEST_TOKEN = "t" * 48
PASSWORD = "Unit-Test-Password-9!Charlie"


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "81" * 32)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    monkeypatch.setenv("SARA_PUBLIC_BASE_URL", "https://sara.example")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("SARA_OAUTH_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", CALLBACK)
    monkeypatch.setenv("SARA_OAUTH_SCOPE", "sara.memory sara.solve")
    monkeypatch.setenv("OWNER_TOKEN", OWNER_TOKEN)
    monkeypatch.setenv("GPT_ACTION_TOKEN", ACTION_TOKEN)
    monkeypatch.setenv("TEST_TOKEN", TEST_TOKEN)


def _oauth_token() -> str:
    store = UserIdentityStore.from_env(required=True)
    assert store is not None
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    account = store.enroll(
        invite_token=invite.token,
        enrollment_id="SARA-NEW-USER",
        password=PASSWORD,
        password_confirm=PASSWORD,
    )
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id=CLIENT_ID,
        redirect_uri=CALLBACK,
        scope="sara.memory sara.solve",
    )
    return store.exchange_authorization_code(
        code=code,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
    ).access_token


def test_oauth_user_cannot_create_owner_enrollment_invitations(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    token = _oauth_token()
    app = FastAPI()
    app.include_router(identity_router)
    response = TestClient(app).post(
        "/admin/enrollment/invitations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_personal_memory_gateway_is_preserved_but_not_exposed_by_custom_gpt_schema():
    schema = Path("chatgpt-gpt-action.yaml").read_text(encoding="utf-8")
    oauth_schema = Path("chatgpt-oauth-action.yaml").read_text(encoding="utf-8")

    assert "/gpt/user/gateway:" not in schema
    assert "saraOmegaUserGateway" not in schema
    assert "memory_status" not in schema
    assert "memory_recall" not in schema
    assert "memory_forget" not in schema

    assert "/gpt/user/gateway:" in oauth_schema
    assert "saraOmegaUserGateway" in oauth_schema
    for operation in ("solve", "memory_status", "memory_recall", "memory_forget"):
        assert f"- {operation}" in oauth_schema
    assert "conversation thread identifier" in oauth_schema.lower()

    for secret_name in (
        "SARA_OAUTH_CLIENT_SECRET",
        "SARA_SOURCE_CONTROL_AUTH_TOKEN",
        "SARA_RAILWAY_CONTROL_AUTH_TOKEN",
    ):
        assert secret_name not in schema
        assert secret_name not in oauth_schema


def test_custom_gpt_schema_does_not_expose_privileged_control_plane():
    schema = Path("chatgpt-gpt-action.yaml").read_text(encoding="utf-8")
    forbidden = (
        "source_control",
        "railway_control",
        "deploy_exact_commit",
        "expected_current_deployment_id",
        "/control-plane",
    )
    lowered = schema.lower()
    for item in forbidden:
        assert item.lower() not in lowered


def test_user_gateway_source_has_no_privileged_control_imports():
    source = Path("app/user_gateway.py").read_text(encoding="utf-8")
    assert "control_plane" not in source
    assert "SARA_SOURCE_CONTROL_AUTH_TOKEN" not in source
    assert "SARA_RAILWAY_CONTROL_AUTH_TOKEN" not in source
    assert "OWNER_TOKEN" not in source
    assert "GPT_ACTION_TOKEN" not in source
    assert "TEST_TOKEN" not in source
