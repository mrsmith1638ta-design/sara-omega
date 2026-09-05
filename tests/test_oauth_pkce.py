from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from app.user_identity import OAuthRejected, UserIdentityStore


CLIENT_ID = "sara-custom-gpt"
CLIENT_SECRET = "oauth-client-secret-123456789"
CALLBACK = "https://chat.openai.com/aip/g-test/oauth/callback"
VERIFIER = "v" * 43


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "61" * 32)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("SARA_OAUTH_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", CALLBACK)
    monkeypatch.setenv("SARA_OAUTH_SCOPE", "sara.memory sara.solve")


def _account(store: UserIdentityStore):
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    return store.enroll(
        invite_token=invite.token,
        enrollment_id="SARA-NEW-USER",
        password="Correct-Horse-7!Battery",
        password_confirm="Correct-Horse-7!Battery",
    )


def test_pkce_s256_is_enforced_only_when_authorization_code_stores_challenge(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _account(store)
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id=CLIENT_ID,
        redirect_uri=CALLBACK,
        scope="sara.memory sara.solve",
        code_challenge=_challenge(VERIFIER),
        code_challenge_method="S256",
    )

    with pytest.raises(OAuthRejected, match="pkce_verifier_rejected"):
        store.exchange_authorization_code(
            code=code,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=CALLBACK,
            code_verifier="wrong" * 11,
        )

    bundle = store.exchange_authorization_code(
        code=code,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
        code_verifier=VERIFIER,
    )
    assert bundle.access_token


def test_confidential_client_code_without_pkce_still_redeems(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _account(store)
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id=CLIENT_ID,
        redirect_uri=CALLBACK,
        scope="sara.memory",
    )

    bundle = store.exchange_authorization_code(
        code=code,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
    )
    assert bundle.access_token


def test_invalid_pkce_method_fails_closed_before_code_issuance(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    account = _account(store)

    with pytest.raises(OAuthRejected, match="invalid_pkce_method"):
        store.issue_authorization_code(
            user_uuid=account.user_uuid,
            client_id=CLIENT_ID,
            redirect_uri=CALLBACK,
            scope="sara.memory",
            code_challenge=_challenge(VERIFIER),
            code_challenge_method="plain",
        )
