from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta

from .user_identity import IdentityStoreError, OAuthRejected, UserIdentityStore, _utc_iso, _utc_now


@dataclass(frozen=True)
class OAuthConsentResult:
    approved: bool
    redirect_uri: str
    state: str
    code: str = ""


class OAuthUserIdentityStore(UserIdentityStore):
    """OAuth hardening extension over SARA's canonical identity database."""

    CONSENT_VERSION = "2026-09-05.v1"
    _PKCE_CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
    _PKCE_VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")

    def _initialize(self) -> None:
        super()._initialize()
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS oauth_authorization_sessions(
                            session_hash TEXT PRIMARY KEY,
                            user_uuid TEXT NOT NULL,
                            client_id TEXT NOT NULL,
                            redirect_uri TEXT NOT NULL,
                            scope TEXT NOT NULL,
                            state TEXT NOT NULL,
                            code_challenge TEXT,
                            code_challenge_method TEXT,
                            expires_at TEXT NOT NULL,
                            consumed_at TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(user_uuid) REFERENCES users(user_uuid)
                        )"""
                    )
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS oauth_consents(
                            consent_id TEXT PRIMARY KEY,
                            user_uuid TEXT NOT NULL,
                            client_id_hash TEXT NOT NULL,
                            scope TEXT NOT NULL,
                            decision TEXT NOT NULL,
                            consent_version TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(user_uuid) REFERENCES users(user_uuid)
                        )"""
                    )
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS oauth_pkce_bindings(
                            code_hash TEXT PRIMARY KEY,
                            code_challenge TEXT NOT NULL,
                            code_challenge_method TEXT NOT NULL,
                            created_at TEXT NOT NULL
                        )"""
                    )
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_extension_initialization_failed") from exc

    def validate_pkce_parameters(self, code_challenge: str, code_challenge_method: str) -> tuple[str, str]:
        challenge = code_challenge.strip()
        method = code_challenge_method.strip()
        if not challenge and not method:
            return "", ""
        if method != "S256":
            raise OAuthRejected("invalid_pkce_method")
        if not challenge or not self._PKCE_CHALLENGE_RE.fullmatch(challenge):
            raise OAuthRejected("invalid_pkce_challenge")
        return challenge, method

    @classmethod
    def _verify_pkce(cls, challenge: str, verifier: str) -> bool:
        if not cls._PKCE_VERIFIER_RE.fullmatch(verifier):
            return False
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        actual = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return hmac.compare_digest(actual, challenge)

    def create_authorization_session(
        self,
        *,
        user_uuid: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        code_challenge: str = "",
        code_challenge_method: str = "",
    ) -> str:
        if not state or not state.strip() or len(state) > 2048:
            raise OAuthRejected("missing_state")
        canonical_scope = self.validate_authorization_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type="code",
            scope=scope,
        )
        challenge, method = self.validate_pkce_parameters(code_challenge, code_challenge_method)
        session = secrets.token_urlsafe(32)
        now = _utc_now()
        config = self.oauth_configuration()
        try:
            with closing(self._connect()) as conn:
                user = conn.execute("SELECT status FROM users WHERE user_uuid=?", (user_uuid,)).fetchone()
                if user is None or str(user["status"]) != "ACTIVE":
                    raise OAuthRejected("oauth_user_rejected")
                with conn:
                    conn.execute(
                        """INSERT INTO oauth_authorization_sessions(
                            session_hash,user_uuid,client_id,redirect_uri,scope,state,
                            code_challenge,code_challenge_method,expires_at,consumed_at,created_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            self._token_hash(session),
                            user_uuid,
                            client_id,
                            redirect_uri,
                            canonical_scope,
                            state,
                            challenge or None,
                            method or None,
                            _utc_iso(now + timedelta(seconds=config.code_ttl_seconds)),
                            None,
                            _utc_iso(now),
                        ),
                    )
        except OAuthRejected:
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_authorization_session_write_failed") from exc
        return session

    def complete_authorization_session(self, authorization_session: str, decision: str) -> OAuthConsentResult:
        normalized_decision = decision.strip().lower()
        if normalized_decision not in {"approve", "deny"}:
            raise OAuthRejected("consent_required")
        session_hash = self._token_hash(authorization_session)
        now = _utc_now()
        now_iso = _utc_iso(now)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM oauth_authorization_sessions WHERE session_hash=?",
                    (session_hash,),
                ).fetchone()
                if row is None or row["consumed_at"] is not None:
                    conn.rollback()
                    raise OAuthRejected("consent_required")
                try:
                    expires_at = datetime.fromisoformat(str(row["expires_at"]))
                except ValueError as exc:
                    conn.rollback()
                    raise OAuthRejected("consent_required") from exc
                if expires_at <= now:
                    conn.rollback()
                    raise OAuthRejected("consent_required")
                user = conn.execute("SELECT status FROM users WHERE user_uuid=?", (str(row["user_uuid"]),)).fetchone()
                if user is None or str(user["status"]) != "ACTIVE":
                    conn.rollback()
                    raise OAuthRejected("oauth_user_rejected")

                canonical_scope = self.validate_authorization_request(
                    client_id=str(row["client_id"]),
                    redirect_uri=str(row["redirect_uri"]),
                    response_type="code",
                    scope=str(row["scope"]),
                )
                challenge = str(row["code_challenge"] or "")
                method = str(row["code_challenge_method"] or "")
                self.validate_pkce_parameters(challenge, method)

                changed = conn.execute(
                    "UPDATE oauth_authorization_sessions SET consumed_at=? WHERE session_hash=? AND consumed_at IS NULL",
                    (now_iso, session_hash),
                )
                if changed.rowcount != 1:
                    conn.rollback()
                    raise OAuthRejected("consent_required")
                conn.execute(
                    """INSERT INTO oauth_consents(
                        consent_id,user_uuid,client_id_hash,scope,decision,consent_version,created_at
                    ) VALUES(?,?,?,?,?,?,?)""",
                    (
                        str(uuid.uuid4()),
                        str(row["user_uuid"]),
                        self._client_id_hash(str(row["client_id"])),
                        canonical_scope,
                        "APPROVED" if normalized_decision == "approve" else "DENIED",
                        self.CONSENT_VERSION,
                        now_iso,
                    ),
                )

                code = ""
                if normalized_decision == "approve":
                    config = self.oauth_configuration()
                    code = secrets.token_urlsafe(32)
                    code_hash = self._token_hash(code)
                    conn.execute(
                        """INSERT INTO oauth_codes(
                            code_hash,user_uuid,client_id_hash,redirect_uri_hash,scope,
                            expires_at,consumed_at,created_at
                        ) VALUES(?,?,?,?,?,?,?,?)""",
                        (
                            code_hash,
                            str(row["user_uuid"]),
                            self._client_id_hash(str(row["client_id"])),
                            self._redirect_uri_hash(str(row["redirect_uri"])),
                            canonical_scope,
                            _utc_iso(now + timedelta(seconds=config.code_ttl_seconds)),
                            None,
                            now_iso,
                        ),
                    )
                    if challenge:
                        conn.execute(
                            "INSERT INTO oauth_pkce_bindings VALUES(?,?,?,?)",
                            (code_hash, challenge, method, now_iso),
                        )
                conn.commit()
                return OAuthConsentResult(
                    approved=normalized_decision == "approve",
                    redirect_uri=str(row["redirect_uri"]),
                    state=str(row["state"]),
                    code=code,
                )
        except OAuthRejected:
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_consent_write_failed") from exc

    def issue_authorization_code(
        self,
        *,
        user_uuid: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: str = "",
        code_challenge_method: str = "",
    ) -> str:
        challenge, method = self.validate_pkce_parameters(code_challenge, code_challenge_method)
        code = super().issue_authorization_code(
            user_uuid=user_uuid,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
        )
        if not challenge:
            return code
        code_hash = self._token_hash(code)
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        "INSERT INTO oauth_pkce_bindings VALUES(?,?,?,?)",
                        (code_hash, challenge, method, _utc_iso()),
                    )
        except sqlite3.Error as exc:
            try:
                with closing(self._connect()) as cleanup:
                    with cleanup:
                        cleanup.execute("DELETE FROM oauth_codes WHERE code_hash=?", (code_hash,))
            except sqlite3.Error:
                pass
            raise IdentityStoreError("oauth_pkce_write_failed") from exc
        return code

    def exchange_authorization_code(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code_verifier: str = "",
    ):
        code_hash = self._token_hash(code)
        try:
            with closing(self._connect()) as conn:
                binding = conn.execute(
                    "SELECT code_challenge,code_challenge_method FROM oauth_pkce_bindings WHERE code_hash=?",
                    (code_hash,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_pkce_read_failed") from exc
        if binding is not None:
            challenge = str(binding["code_challenge"])
            method = str(binding["code_challenge_method"])
            if method != "S256" or not self._verify_pkce(challenge, code_verifier):
                raise OAuthRejected("pkce_verifier_rejected")

        bundle = super().exchange_authorization_code(
            code=code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        if binding is not None:
            try:
                with closing(self._connect()) as conn:
                    with conn:
                        conn.execute("DELETE FROM oauth_pkce_bindings WHERE code_hash=?", (code_hash,))
            except sqlite3.Error:
                pass
        return bundle
