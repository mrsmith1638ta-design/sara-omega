from __future__ import annotations

from pathlib import Path

import pytest

from app.user_identity import OAuthConfigurationError, OAuthRejected, UserIdentityStore


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "41" * 32)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_ID", "sara-custom-gpt")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_SECRET", "oauth-client-secret-123456789")
    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", "https://chat.openai.com/aip/g-test/oauth/callback")
    monkeypatch.setenv("SARA_OAUTH_SCOPE", "sara.memory sara.solve")
    monkeypatch.setenv("SARA_OAUTH_CODE_TTL_SECONDS", "300")
    monkeypatch.setenv("SARA_OAUTH_ACCESS_TTL_SECONDS", "3600")
    monkeypatch.setenv("SARA_OAUTH_REFRESH_TTL_SECONDS", "2592000")
    monkeypatch.setenv("SARA_AUTH_MAX_FAILURES", "5")
    monkeypatch.setenv("SARA_AUTH_FAILURE_WINDOW_SECONDS", "900")
    monkeypatch.setenv("SARA_AUTH_LOCK_SECONDS", "900")


def _account(store: UserIdentityStore):
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    return store.enroll(
        invite_token=invite.token,
        enrollment_id="SARA-NEW-USER",
        password="Correct-Horse-7!Battery",
        password_confirm="Correct-Horse-7!Battery",
    )


def test_oauth_configuration_requires_exact_https_redirects(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    config = store.oauth_configuration()
    assert config.client_id == "sara-custom-gpt"
    assert config.redirect_uris == ("https://chat.openai.com/aip/g-test/oauth/callback",)
    assert config.scopes == frozenset({"sara.memory", "sara.solve"})

    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", "https://chat.openai.com/*")
    with pytest.raises(OAuthConfigurationError, match="oauth_redirect_uri_invalid"):
        UserIdentityStore.from_env(required=True).oauth_configuration()

    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", "http://chat.openai.com/aip/g-test/oauth/callback")
    with pytest.raises(OAuthConfigurationError, match="oauth_redirect_uri_invalid"):
        UserIdentityStore.from_env(required=True).oauth_configuration()


def test_authorization_request_is_exact_and_scope_bounded(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    scope = store.validate_authorization_request(
        client_id="sara-custom-gpt",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        response_type="code",
        scope="sara.solve sara.memory",
    )
    assert scope == "sara.memory sara.solve"

    with pytest.raises(OAuthRejected, match="oauth_redirect_uri_rejected"):
        store.validate_authorization_request(
            client_id="sara-custom-gpt",
            redirect_uri="https://evil.example/callback",
            response_type="code",
            scope="sara.memory",
        )
    with pytest.raises(OAuthRejected, match="oauth_scope_rejected"):
        store.validate_authorization_request(
            client_id="sara-custom-gpt",
            redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
            response_type="code",
            scope="sara.admin",
        )


def test_authorization_code_is_single_use_and_tokens_are_opaque(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _account(store)
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id="sara-custom-gpt",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        scope="sara.memory sara.solve",
    )
    assert len(code) >= 32

    bundle = store.exchange_authorization_code(
        code=code,
        client_id="sara-custom-gpt",
        client_secret="oauth-client-secret-123456789",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
    )
    assert bundle.token_type == "Bearer"
    assert bundle.expires_in == 3600
    assert bundle.access_token != bundle.refresh_token
    principal = store.resolve_access_token(bundle.access_token)
    assert principal.user_uuid == account.user_uuid
    assert principal.public_user_id == account.public_user_id
    assert principal.scope == "sara.memory sara.solve"

    with pytest.raises(OAuthRejected, match="authorization_code_rejected"):
        store.exchange_authorization_code(
            code=code,
            client_id="sara-custom-gpt",
            client_secret="oauth-client-secret-123456789",
            redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        )

    raw = (tmp_path / "sara_identity.db").read_bytes()
    assert code.encode() not in raw
    assert bundle.access_token.encode() not in raw
    assert bundle.refresh_token.encode() not in raw
    assert b"oauth-client-secret-123456789" not in raw


def test_wrong_client_secret_and_redirect_fail_closed(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _account(store)
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id="sara-custom-gpt",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        scope="sara.memory",
    )
    with pytest.raises(OAuthRejected, match="oauth_client_rejected"):
        store.exchange_authorization_code(
            code=code,
            client_id="sara-custom-gpt",
            client_secret="wrong-secret",
            redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        )
    with pytest.raises(OAuthRejected, match="oauth_redirect_uri_rejected"):
        store.exchange_authorization_code(
            code=code,
            client_id="sara-custom-gpt",
            client_secret="oauth-client-secret-123456789",
            redirect_uri="https://evil.example/callback",
        )


def test_refresh_token_rotates_and_replay_is_rejected(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _account(store)
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id="sara-custom-gpt",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        scope="sara.solve",
    )
    first = store.exchange_authorization_code(
        code=code,
        client_id="sara-custom-gpt",
        client_secret="oauth-client-secret-123456789",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
    )
    second = store.refresh_access_token(
        refresh_token=first.refresh_token,
        client_id="sara-custom-gpt",
        client_secret="oauth-client-secret-123456789",
    )
    assert second.refresh_token != first.refresh_token
    assert second.access_token != first.access_token
    with pytest.raises(OAuthRejected, match="refresh_token_rejected"):
        store.refresh_access_token(
            refresh_token=first.refresh_token,
            client_id="sara-custom-gpt",
            client_secret="oauth-client-secret-123456789",
        )


def test_access_token_revocation_survives_restart(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    first_store = UserIdentityStore.from_env(required=True)
    account = _account(first_store)
    code = first_store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id="sara-custom-gpt",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
        scope="sara.memory",
    )
    bundle = first_store.exchange_authorization_code(
        code=code,
        client_id="sara-custom-gpt",
        client_secret="oauth-client-secret-123456789",
        redirect_uri="https://chat.openai.com/aip/g-test/oauth/callback",
    )
    first_store.revoke_token(
        token=bundle.access_token,
        client_id="sara-custom-gpt",
        client_secret="oauth-client-secret-123456789",
    )
    second_store = UserIdentityStore.from_env(required=True)
    with pytest.raises(OAuthRejected, match="access_token_rejected"):
        second_store.resolve_access_token(bundle.access_token)


def test_password_bruteforce_lockout_is_durable(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    first_store = UserIdentityStore.from_env(required=True)
    account = _account(first_store)
    for _ in range(5):
        with pytest.raises(OAuthRejected, match="authentication_rejected"):
            first_store.authenticate_for_oauth(account.public_user_id, "Wrong-Password-9!")

    second_store = UserIdentityStore.from_env(required=True)
    with pytest.raises(OAuthRejected, match="authentication_locked"):
        second_store.authenticate_for_oauth(account.public_user_id, "Correct-Horse-7!Battery")


def test_oauth_configuration_missing_callback_is_explicitly_not_ready(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    monkeypatch.delenv("SARA_OAUTH_REDIRECT_URIS", raising=False)
    store = UserIdentityStore.from_env(required=True)
    status = store.oauth_status()
    assert status["configured"] is False
    assert status["status"] == "CONFIGURATION_REQUIRED"
    assert status["client_id_configured"] is True
    assert status["client_secret_configured"] is True
    assert status["redirect_uris_configured"] is False
