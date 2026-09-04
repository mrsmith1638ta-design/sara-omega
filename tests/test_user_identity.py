from __future__ import annotations

from pathlib import Path

import pytest

from app.memory import derive_secret_key
from app.user_identity import (
    EnrollmentRejected,
    PasswordPolicyRejected,
    UserIdentityStore,
)


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "31" * 32)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    monkeypatch.delenv("SARA_MEMORY_KEY_B64", raising=False)
    monkeypatch.delenv("SARA_FAILSAFE_MASTER_KEY_HEX", raising=False)
    monkeypatch.delenv("SARA_FAILSAFE_MASTER_KEY_B64", raising=False)


def test_secret_derivation_is_domain_separated(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    password_key = derive_secret_key("identity-password-pepper", required=True)
    token_key = derive_secret_key("identity-token-hash", required=True)
    assert password_key is not None
    assert token_key is not None
    assert password_key != token_key
    assert len(password_key) == 32
    assert len(token_key) == 32


def test_invitation_enrollment_is_single_use_and_secrets_are_not_plaintext(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    invitation = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    password = "Correct-Horse-7!Battery"

    account = store.enroll(
        invite_token=invitation.token,
        enrollment_id="SARA-NEW-USER",
        password=password,
        password_confirm=password,
    )

    assert account.public_user_id.startswith("SARA-U-")
    assert len(account.public_user_id) == len("SARA-U-") + 12
    assert account.status == "ACTIVE"
    assert store.authenticate_password(account.public_user_id, password).user_uuid == account.user_uuid

    with pytest.raises(EnrollmentRejected, match="invitation_not_available"):
        store.enroll(
            invite_token=invitation.token,
            enrollment_id="SARA-NEW-USER",
            password=password,
            password_confirm=password,
        )

    raw = (tmp_path / "sara_identity.db").read_bytes()
    assert invitation.token.encode("utf-8") not in raw
    assert b"SARA-NEW-USER" not in raw
    assert password.encode("utf-8") not in raw


def test_generic_enrollment_id_is_not_a_login_identity(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    with pytest.raises(EnrollmentRejected, match="authentication_rejected"):
        store.authenticate_password("SARA-NEW-USER", "Correct-Horse-7!Battery")


def test_password_confirmation_and_policy_fail_closed(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    invitation = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)

    with pytest.raises(PasswordPolicyRejected, match="password_confirmation_mismatch"):
        store.enroll(
            invite_token=invitation.token,
            enrollment_id="SARA-NEW-USER",
            password="Correct-Horse-7!Battery",
            password_confirm="Correct-Horse-7!Batterx",
        )

    with pytest.raises(PasswordPolicyRejected, match="password_policy_rejected"):
        store.enroll(
            invite_token=invitation.token,
            enrollment_id="SARA-NEW-USER",
            password="passwordpassword",
            password_confirm="passwordpassword",
        )


def test_expired_invitation_is_rejected(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    invitation = store.create_invitation(base_url="https://sara.example", ttl_seconds=-1)

    with pytest.raises(EnrollmentRejected, match="invitation_expired"):
        store.enroll(
            invite_token=invitation.token,
            enrollment_id="SARA-NEW-USER",
            password="Correct-Horse-7!Battery",
            password_confirm="Correct-Horse-7!Battery",
        )


def test_wrong_enrollment_id_does_not_consume_invitation(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    store = UserIdentityStore.from_env(required=True)
    invitation = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)

    with pytest.raises(EnrollmentRejected, match="enrollment_id_rejected"):
        store.enroll(
            invite_token=invitation.token,
            enrollment_id="NOT-SARA",
            password="Correct-Horse-7!Battery",
            password_confirm="Correct-Horse-7!Battery",
        )

    account = store.enroll(
        invite_token=invitation.token,
        enrollment_id="SARA-NEW-USER",
        password="Correct-Horse-7!Battery",
        password_confirm="Correct-Horse-7!Battery",
    )
    assert account.status == "ACTIVE"


def test_identity_store_recovers_after_restart(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    first = UserIdentityStore.from_env(required=True)
    invitation = first.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    account = first.enroll(
        invite_token=invitation.token,
        enrollment_id="SARA-NEW-USER",
        password="Correct-Horse-7!Battery",
        password_confirm="Correct-Horse-7!Battery",
    )

    second = UserIdentityStore.from_env(required=True)
    recovered = second.authenticate_password(account.public_user_id, "Correct-Horse-7!Battery")
    assert recovered.user_uuid == account.user_uuid
    assert recovered.public_user_id == account.public_user_id
