from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .memory import derive_secret_key


class IdentityStoreError(RuntimeError):
    """Raised when durable user identity state cannot be read or written safely."""


class EnrollmentRejected(IdentityStoreError):
    """Raised when enrollment or user authentication must fail closed."""


class PasswordPolicyRejected(EnrollmentRejected):
    """Raised when a proposed password does not satisfy SARA's password contract."""


class OAuthRejected(IdentityStoreError):
    """Raised when an OAuth request or credential must fail closed."""


class OAuthConfigurationError(OAuthRejected):
    """Raised when the SARA OAuth provider is not safely configured."""


@dataclass(frozen=True)
class AccountRecord:
    user_uuid: str
    public_user_id: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class InvitationRecord:
    token: str
    enrollment_id: str
    enrollment_url: str
    expires_at: str


@dataclass(frozen=True)
class OAuthConfiguration:
    client_id: str
    client_secret: str
    redirect_uris: tuple[str, ...]
    scopes: frozenset[str]
    code_ttl_seconds: int
    access_ttl_seconds: int
    refresh_ttl_seconds: int


@dataclass(frozen=True)
class OAuthTokenBundle:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    scope: str


@dataclass(frozen=True)
class OAuthPrincipal:
    user_uuid: str
    public_user_id: str
    scope: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat()


def _data_dir() -> Path:
    data_dir = Path(os.getenv("SARA_DATA_DIR", "./data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(data_dir, 0o700)
    except OSError:
        pass
    return data_dir


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def _validate_password(password: str, password_confirm: str) -> None:
    if not hmac.compare_digest(password, password_confirm):
        raise PasswordPolicyRejected("password_confirmation_mismatch")
    if len(password) < 12 or len(password) > 128:
        raise PasswordPolicyRejected("password_policy_rejected")
    classes = (
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"[0-9]", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    )
    if sum(classes) < 3:
        raise PasswordPolicyRejected("password_policy_rejected")


def _validated_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise EnrollmentRejected("invalid_public_base_url")
    if parsed.query or parsed.fragment:
        raise EnrollmentRejected("invalid_public_base_url")
    return normalized


def _validated_redirect_uri(value: str) -> str:
    redirect = value.strip()
    parsed = urlsplit(redirect)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or "*" in redirect
        or parsed.fragment
    ):
        raise OAuthConfigurationError("oauth_redirect_uri_invalid")
    return redirect


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise OAuthConfigurationError(f"oauth_configuration_invalid:{name}") from exc
    if value <= 0:
        raise OAuthConfigurationError(f"oauth_configuration_invalid:{name}")
    return value


class UserIdentityStore:
    """Durable SARA account, enrollment, OAuth, and login-defense store."""

    SCRYPT_N = 32768
    SCRYPT_R = 8
    SCRYPT_P = 1
    SCRYPT_DKLEN = 32
    SCRYPT_MAXMEM = 128 * 1024 * 1024

    def __init__(
        self,
        db: Path,
        *,
        password_pepper: bytes,
        token_hash_key: bytes,
        enrollment_hash_key: bytes,
        enrollment_id: str,
    ):
        self.db = db
        self._password_pepper = password_pepper
        self._token_hash_key = token_hash_key
        self._enrollment_hash_key = enrollment_hash_key
        self.enrollment_id = enrollment_id
        self._initialize()

    @classmethod
    def from_env(cls, *, required: bool = True) -> "UserIdentityStore | None":
        password_pepper = derive_secret_key("identity-password-pepper", required=required)
        token_hash_key = derive_secret_key("identity-token-hash", required=required)
        enrollment_hash_key = derive_secret_key("identity-enrollment-hash", required=required)
        if password_pepper is None or token_hash_key is None or enrollment_hash_key is None:
            return None
        enrollment_id = os.getenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER").strip() or "SARA-NEW-USER"
        if len(enrollment_id) > 128:
            raise IdentityStoreError("invalid_enrollment_id_configuration")
        return cls(
            _data_dir() / "sara_identity.db",
            password_pepper=password_pepper,
            token_hash_key=token_hash_key,
            enrollment_hash_key=enrollment_hash_key,
            enrollment_id=enrollment_id,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _initialize(self) -> None:
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS users(
                            user_uuid TEXT PRIMARY KEY,
                            public_user_id TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            status TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        )"""
                    )
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS enrollment_invites(
                            token_hash TEXT PRIMARY KEY,
                            enrollment_id_hash TEXT NOT NULL,
                            expires_at TEXT NOT NULL,
                            consumed_at TEXT,
                            user_uuid TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(user_uuid) REFERENCES users(user_uuid)
                        )"""
                    )
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS oauth_codes(
                            code_hash TEXT PRIMARY KEY,
                            user_uuid TEXT NOT NULL,
                            client_id_hash TEXT NOT NULL,
                            redirect_uri_hash TEXT NOT NULL,
                            scope TEXT NOT NULL,
                            expires_at TEXT NOT NULL,
                            consumed_at TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(user_uuid) REFERENCES users(user_uuid)
                        )"""
                    )
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS oauth_tokens(
                            token_hash TEXT PRIMARY KEY,
                            token_type TEXT NOT NULL,
                            user_uuid TEXT NOT NULL,
                            client_id_hash TEXT NOT NULL,
                            scope TEXT NOT NULL,
                            expires_at TEXT NOT NULL,
                            revoked_at TEXT,
                            parent_hash TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(user_uuid) REFERENCES users(user_uuid)
                        )"""
                    )
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS auth_failures(
                            subject_hash TEXT PRIMARY KEY,
                            failure_count INTEGER NOT NULL,
                            window_started_at TEXT NOT NULL,
                            locked_until TEXT,
                            updated_at TEXT NOT NULL
                        )"""
                    )
        except sqlite3.Error as exc:
            raise IdentityStoreError("identity_store_initialization_failed") from exc
        try:
            os.chmod(self.db, 0o600)
        except OSError:
            pass

    @staticmethod
    def _row_to_account(row: sqlite3.Row) -> AccountRecord:
        return AccountRecord(
            user_uuid=str(row["user_uuid"]),
            public_user_id=str(row["public_user_id"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _secret_hash(self, namespace: str, value: str) -> str:
        return hmac.new(
            self._token_hash_key,
            f"{namespace}\0{value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _token_hash(self, token: str) -> str:
        return self._secret_hash("token", token)

    def _client_id_hash(self, client_id: str) -> str:
        return self._secret_hash("oauth-client-id", client_id)

    def _redirect_uri_hash(self, redirect_uri: str) -> str:
        return self._secret_hash("oauth-redirect-uri", redirect_uri)

    def _auth_subject_hash(self, public_user_id: str) -> str:
        return self._secret_hash("auth-subject", public_user_id)

    def _enrollment_hash(self, enrollment_id: str) -> str:
        return hmac.new(self._enrollment_hash_key, enrollment_id.encode("utf-8"), hashlib.sha256).hexdigest()

    def _password_hash(self, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.scrypt(
            password.encode("utf-8") + b"\0" + self._password_pepper,
            salt=salt,
            n=self.SCRYPT_N,
            r=self.SCRYPT_R,
            p=self.SCRYPT_P,
            dklen=self.SCRYPT_DKLEN,
            maxmem=self.SCRYPT_MAXMEM,
        )
        return (
            f"scrypt$v=1$n={self.SCRYPT_N}$r={self.SCRYPT_R}$p={self.SCRYPT_P}$"
            f"{_b64encode(salt)}${_b64encode(digest)}"
        )

    def _verify_password_hash(self, password: str, encoded: str) -> bool:
        try:
            parts = encoded.split("$")
            if len(parts) != 7 or parts[0] != "scrypt" or parts[1] != "v=1":
                return False
            n = int(parts[2].split("=", 1)[1])
            r = int(parts[3].split("=", 1)[1])
            p = int(parts[4].split("=", 1)[1])
            salt = _b64decode(parts[5])
            expected = _b64decode(parts[6])
        except (ValueError, IndexError, TypeError):
            return False
        if n != self.SCRYPT_N or r != self.SCRYPT_R or p != self.SCRYPT_P:
            return False
        try:
            actual = hashlib.scrypt(
                password.encode("utf-8") + b"\0" + self._password_pepper,
                salt=salt,
                n=n,
                r=r,
                p=p,
                dklen=len(expected),
                maxmem=self.SCRYPT_MAXMEM,
            )
        except (ValueError, MemoryError):
            return False
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def _generate_public_user_id() -> str:
        return "SARA-U-" + secrets.token_hex(6).upper()

    def create_invitation(self, *, base_url: str, ttl_seconds: int | None = None) -> InvitationRecord:
        public_base = _validated_base_url(base_url)
        ttl = int(ttl_seconds if ttl_seconds is not None else os.getenv("SARA_INVITE_TTL_SECONDS", "86400"))
        token = secrets.token_urlsafe(32)
        token_hash = self._token_hash(token)
        enrollment_hash = self._enrollment_hash(self.enrollment_id)
        now = _utc_now()
        expires = now + timedelta(seconds=ttl)
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        """INSERT INTO enrollment_invites(
                            token_hash,enrollment_id_hash,expires_at,consumed_at,user_uuid,created_at
                        ) VALUES(?,?,?,?,?,?)""",
                        (token_hash, enrollment_hash, _utc_iso(expires), None, None, _utc_iso(now)),
                    )
        except sqlite3.Error as exc:
            raise IdentityStoreError("invitation_write_failed") from exc
        return InvitationRecord(
            token=token,
            enrollment_id=self.enrollment_id,
            enrollment_url=f"{public_base}/enroll/{token}",
            expires_at=_utc_iso(expires),
        )

    def enroll(
        self,
        *,
        invite_token: str,
        enrollment_id: str,
        password: str,
        password_confirm: str,
    ) -> AccountRecord:
        _validate_password(password, password_confirm)
        token_hash = self._token_hash(invite_token)
        supplied_enrollment_hash = self._enrollment_hash(enrollment_id)
        now = _utc_now()
        now_iso = _utc_iso(now)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM enrollment_invites WHERE token_hash=?",
                    (token_hash,),
                ).fetchone()
                if row is None or row["consumed_at"] is not None:
                    conn.rollback()
                    raise EnrollmentRejected("invitation_not_available")
                if not hmac.compare_digest(str(row["enrollment_id_hash"]), supplied_enrollment_hash):
                    conn.rollback()
                    raise EnrollmentRejected("enrollment_id_rejected")
                try:
                    expires_at = datetime.fromisoformat(str(row["expires_at"]))
                except ValueError as exc:
                    conn.rollback()
                    raise EnrollmentRejected("invitation_state_invalid") from exc
                if expires_at <= now:
                    conn.rollback()
                    raise EnrollmentRejected("invitation_expired")

                password_hash = self._password_hash(password)
                account: AccountRecord | None = None
                for _ in range(8):
                    user_uuid = str(uuid.uuid4())
                    public_user_id = self._generate_public_user_id()
                    try:
                        conn.execute(
                            "INSERT INTO users VALUES(?,?,?,?,?,?)",
                            (user_uuid, public_user_id, password_hash, "ACTIVE", now_iso, now_iso),
                        )
                    except sqlite3.IntegrityError:
                        continue
                    account = AccountRecord(
                        user_uuid=user_uuid,
                        public_user_id=public_user_id,
                        status="ACTIVE",
                        created_at=now_iso,
                        updated_at=now_iso,
                    )
                    break
                if account is None:
                    conn.rollback()
                    raise IdentityStoreError("public_user_id_generation_failed")
                updated = conn.execute(
                    """UPDATE enrollment_invites SET consumed_at=?,user_uuid=?
                    WHERE token_hash=? AND consumed_at IS NULL""",
                    (now_iso, account.user_uuid, token_hash),
                )
                if updated.rowcount != 1:
                    conn.rollback()
                    raise EnrollmentRejected("invitation_not_available")
                conn.commit()
                return account
        except IdentityStoreError:
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("enrollment_write_failed") from exc

    def authenticate_password(self, public_user_id: str, password: str) -> AccountRecord:
        if not public_user_id or not password or hmac.compare_digest(public_user_id, self.enrollment_id):
            raise EnrollmentRejected("authentication_rejected")
        try:
            with closing(self._connect()) as conn:
                row = conn.execute("SELECT * FROM users WHERE public_user_id=?", (public_user_id,)).fetchone()
        except sqlite3.Error as exc:
            raise IdentityStoreError("identity_read_failed") from exc
        if row is None or str(row["status"]) != "ACTIVE":
            raise EnrollmentRejected("authentication_rejected")
        if not self._verify_password_hash(password, str(row["password_hash"])):
            raise EnrollmentRejected("authentication_rejected")
        return self._row_to_account(row)

    def oauth_status(self) -> dict[str, object]:
        client_id = bool(os.getenv("SARA_OAUTH_CLIENT_ID", "").strip())
        client_secret = bool(os.getenv("SARA_OAUTH_CLIENT_SECRET", "").strip())
        redirect_raw = os.getenv("SARA_OAUTH_REDIRECT_URIS", "").strip()
        redirect_ready = bool(redirect_raw)
        configured = False
        if client_id and client_secret and redirect_ready:
            try:
                self.oauth_configuration()
                configured = True
            except OAuthConfigurationError:
                configured = False
        return {
            "status": "READY" if configured else "CONFIGURATION_REQUIRED",
            "configured": configured,
            "client_id_configured": client_id,
            "client_secret_configured": client_secret,
            "redirect_uris_configured": redirect_ready,
        }

    def oauth_configuration(self) -> OAuthConfiguration:
        client_id = os.getenv("SARA_OAUTH_CLIENT_ID", "").strip()
        client_secret = os.getenv("SARA_OAUTH_CLIENT_SECRET", "").strip()
        redirect_raw = os.getenv("SARA_OAUTH_REDIRECT_URIS", "").strip()
        scope_raw = os.getenv("SARA_OAUTH_SCOPE", "sara.memory sara.solve").strip()
        if not client_id or not client_secret or not redirect_raw:
            raise OAuthConfigurationError("oauth_configuration_required")
        if len(client_id) > 256 or len(client_secret) < 20 or len(client_secret) > 512:
            raise OAuthConfigurationError("oauth_client_configuration_invalid")
        redirects = tuple(_validated_redirect_uri(item) for item in redirect_raw.split(",") if item.strip())
        if not redirects or len(set(redirects)) != len(redirects):
            raise OAuthConfigurationError("oauth_redirect_uri_invalid")
        scopes = frozenset(item for item in scope_raw.split() if item)
        if not scopes or len(scopes) > 16 or any(len(item) > 128 for item in scopes):
            raise OAuthConfigurationError("oauth_scope_configuration_invalid")
        return OAuthConfiguration(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=redirects,
            scopes=scopes,
            code_ttl_seconds=_positive_int_env("SARA_OAUTH_CODE_TTL_SECONDS", 300),
            access_ttl_seconds=_positive_int_env("SARA_OAUTH_ACCESS_TTL_SECONDS", 3600),
            refresh_ttl_seconds=_positive_int_env("SARA_OAUTH_REFRESH_TTL_SECONDS", 2592000),
        )

    def _validate_client_credentials(self, client_id: str, client_secret: str) -> OAuthConfiguration:
        config = self.oauth_configuration()
        if not hmac.compare_digest(client_id, config.client_id) or not hmac.compare_digest(
            client_secret, config.client_secret
        ):
            raise OAuthRejected("oauth_client_rejected")
        return config

    def validate_authorization_request(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        response_type: str,
        scope: str,
    ) -> str:
        config = self.oauth_configuration()
        if not hmac.compare_digest(client_id, config.client_id):
            raise OAuthRejected("oauth_client_rejected")
        if redirect_uri not in config.redirect_uris:
            raise OAuthRejected("oauth_redirect_uri_rejected")
        if response_type != "code":
            raise OAuthRejected("oauth_response_type_rejected")
        requested = frozenset(item for item in scope.split() if item) if scope.strip() else config.scopes
        if not requested or not requested.issubset(config.scopes):
            raise OAuthRejected("oauth_scope_rejected")
        return " ".join(sorted(requested))

    def issue_authorization_code(
        self,
        *,
        user_uuid: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
    ) -> str:
        canonical_scope = self.validate_authorization_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type="code",
            scope=scope,
        )
        config = self.oauth_configuration()
        code = secrets.token_urlsafe(32)
        now = _utc_now()
        try:
            with closing(self._connect()) as conn:
                user = conn.execute(
                    "SELECT status FROM users WHERE user_uuid=?", (user_uuid,)
                ).fetchone()
                if user is None or str(user["status"]) != "ACTIVE":
                    raise OAuthRejected("oauth_user_rejected")
                with conn:
                    conn.execute(
                        """INSERT INTO oauth_codes(
                            code_hash,user_uuid,client_id_hash,redirect_uri_hash,scope,
                            expires_at,consumed_at,created_at
                        ) VALUES(?,?,?,?,?,?,?,?)""",
                        (
                            self._token_hash(code),
                            user_uuid,
                            self._client_id_hash(client_id),
                            self._redirect_uri_hash(redirect_uri),
                            canonical_scope,
                            _utc_iso(now + timedelta(seconds=config.code_ttl_seconds)),
                            None,
                            _utc_iso(now),
                        ),
                    )
        except OAuthRejected:
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_code_write_failed") from exc
        return code

    def _insert_token_pair(
        self,
        conn: sqlite3.Connection,
        *,
        user_uuid: str,
        client_id: str,
        scope: str,
        parent_hash: str | None,
        config: OAuthConfiguration,
        now: datetime,
    ) -> OAuthTokenBundle:
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        client_hash = self._client_id_hash(client_id)
        created_at = _utc_iso(now)
        conn.execute(
            "INSERT INTO oauth_tokens VALUES(?,?,?,?,?,?,?,?,?)",
            (
                self._token_hash(access_token),
                "ACCESS",
                user_uuid,
                client_hash,
                scope,
                _utc_iso(now + timedelta(seconds=config.access_ttl_seconds)),
                None,
                parent_hash,
                created_at,
            ),
        )
        conn.execute(
            "INSERT INTO oauth_tokens VALUES(?,?,?,?,?,?,?,?,?)",
            (
                self._token_hash(refresh_token),
                "REFRESH",
                user_uuid,
                client_hash,
                scope,
                _utc_iso(now + timedelta(seconds=config.refresh_ttl_seconds)),
                None,
                parent_hash,
                created_at,
            ),
        )
        return OAuthTokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=config.access_ttl_seconds,
            scope=scope,
        )

    def exchange_authorization_code(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> OAuthTokenBundle:
        config = self._validate_client_credentials(client_id, client_secret)
        if redirect_uri not in config.redirect_uris:
            raise OAuthRejected("oauth_redirect_uri_rejected")
        code_hash = self._token_hash(code)
        now = _utc_now()
        now_iso = _utc_iso(now)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM oauth_codes WHERE code_hash=?", (code_hash,)).fetchone()
                if row is None or row["consumed_at"] is not None:
                    conn.rollback()
                    raise OAuthRejected("authorization_code_rejected")
                try:
                    expires_at = datetime.fromisoformat(str(row["expires_at"]))
                except ValueError as exc:
                    conn.rollback()
                    raise OAuthRejected("authorization_code_rejected") from exc
                if expires_at <= now:
                    conn.rollback()
                    raise OAuthRejected("authorization_code_rejected")
                if not hmac.compare_digest(str(row["client_id_hash"]), self._client_id_hash(client_id)):
                    conn.rollback()
                    raise OAuthRejected("oauth_client_rejected")
                if not hmac.compare_digest(
                    str(row["redirect_uri_hash"]), self._redirect_uri_hash(redirect_uri)
                ):
                    conn.rollback()
                    raise OAuthRejected("oauth_redirect_uri_rejected")
                user = conn.execute(
                    "SELECT status FROM users WHERE user_uuid=?", (str(row["user_uuid"]),)
                ).fetchone()
                if user is None or str(user["status"]) != "ACTIVE":
                    conn.rollback()
                    raise OAuthRejected("oauth_user_rejected")
                changed = conn.execute(
                    "UPDATE oauth_codes SET consumed_at=? WHERE code_hash=? AND consumed_at IS NULL",
                    (now_iso, code_hash),
                )
                if changed.rowcount != 1:
                    conn.rollback()
                    raise OAuthRejected("authorization_code_rejected")
                bundle = self._insert_token_pair(
                    conn,
                    user_uuid=str(row["user_uuid"]),
                    client_id=client_id,
                    scope=str(row["scope"]),
                    parent_hash=code_hash,
                    config=config,
                    now=now,
                )
                conn.commit()
                return bundle
        except OAuthRejected:
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_exchange_failed") from exc

    def refresh_access_token(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> OAuthTokenBundle:
        config = self._validate_client_credentials(client_id, client_secret)
        token_hash = self._token_hash(refresh_token)
        now = _utc_now()
        now_iso = _utc_iso(now)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM oauth_tokens WHERE token_hash=?", (token_hash,)).fetchone()
                if row is None or str(row["token_type"]) != "REFRESH" or row["revoked_at"] is not None:
                    conn.rollback()
                    raise OAuthRejected("refresh_token_rejected")
                try:
                    expires_at = datetime.fromisoformat(str(row["expires_at"]))
                except ValueError as exc:
                    conn.rollback()
                    raise OAuthRejected("refresh_token_rejected") from exc
                if expires_at <= now:
                    conn.rollback()
                    raise OAuthRejected("refresh_token_rejected")
                if not hmac.compare_digest(str(row["client_id_hash"]), self._client_id_hash(client_id)):
                    conn.rollback()
                    raise OAuthRejected("oauth_client_rejected")
                user = conn.execute(
                    "SELECT status FROM users WHERE user_uuid=?", (str(row["user_uuid"]),)
                ).fetchone()
                if user is None or str(user["status"]) != "ACTIVE":
                    conn.rollback()
                    raise OAuthRejected("oauth_user_rejected")
                changed = conn.execute(
                    "UPDATE oauth_tokens SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                    (now_iso, token_hash),
                )
                if changed.rowcount != 1:
                    conn.rollback()
                    raise OAuthRejected("refresh_token_rejected")
                bundle = self._insert_token_pair(
                    conn,
                    user_uuid=str(row["user_uuid"]),
                    client_id=client_id,
                    scope=str(row["scope"]),
                    parent_hash=token_hash,
                    config=config,
                    now=now,
                )
                conn.commit()
                return bundle
        except OAuthRejected:
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_refresh_failed") from exc

    def resolve_access_token(self, access_token: str) -> OAuthPrincipal:
        token_hash = self._token_hash(access_token)
        now = _utc_now()
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """SELECT t.*,u.public_user_id,u.status AS user_status
                    FROM oauth_tokens t JOIN users u ON u.user_uuid=t.user_uuid
                    WHERE t.token_hash=?""",
                    (token_hash,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_token_read_failed") from exc
        if row is None or str(row["token_type"]) != "ACCESS" or row["revoked_at"] is not None:
            raise OAuthRejected("access_token_rejected")
        try:
            expires_at = datetime.fromisoformat(str(row["expires_at"]))
        except ValueError as exc:
            raise OAuthRejected("access_token_rejected") from exc
        if expires_at <= now or str(row["user_status"]) != "ACTIVE":
            raise OAuthRejected("access_token_rejected")
        return OAuthPrincipal(
            user_uuid=str(row["user_uuid"]),
            public_user_id=str(row["public_user_id"]),
            scope=str(row["scope"]),
        )

    def revoke_token(self, *, token: str, client_id: str, client_secret: str) -> None:
        self._validate_client_credentials(client_id, client_secret)
        token_hash = self._token_hash(token)
        client_hash = self._client_id_hash(client_id)
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        """UPDATE oauth_tokens SET revoked_at=?
                        WHERE token_hash=? AND client_id_hash=? AND revoked_at IS NULL""",
                        (_utc_iso(), token_hash, client_hash),
                    )
        except sqlite3.Error as exc:
            raise IdentityStoreError("oauth_revoke_failed") from exc

    def _lockout_values(self) -> tuple[int, int, int]:
        try:
            maximum = int(os.getenv("SARA_AUTH_MAX_FAILURES", "5"))
            window = int(os.getenv("SARA_AUTH_FAILURE_WINDOW_SECONDS", "900"))
            lock = int(os.getenv("SARA_AUTH_LOCK_SECONDS", "900"))
        except ValueError as exc:
            raise IdentityStoreError("auth_lockout_configuration_invalid") from exc
        if maximum < 1 or window < 1 or lock < 1:
            raise IdentityStoreError("auth_lockout_configuration_invalid")
        return maximum, window, lock

    def _assert_not_locked(self, conn: sqlite3.Connection, subject_hash: str, now: datetime) -> None:
        row = conn.execute("SELECT locked_until FROM auth_failures WHERE subject_hash=?", (subject_hash,)).fetchone()
        if row is None or not row["locked_until"]:
            return
        try:
            locked_until = datetime.fromisoformat(str(row["locked_until"]))
        except ValueError as exc:
            raise OAuthRejected("authentication_locked") from exc
        if locked_until > now:
            raise OAuthRejected("authentication_locked")

    def _record_auth_failure(self, public_user_id: str, now: datetime) -> None:
        maximum, window_seconds, lock_seconds = self._lockout_values()
        subject_hash = self._auth_subject_hash(public_user_id)
        now_iso = _utc_iso(now)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM auth_failures WHERE subject_hash=?", (subject_hash,)).fetchone()
                if row is None:
                    count = 1
                    window_start = now
                else:
                    try:
                        window_start = datetime.fromisoformat(str(row["window_started_at"]))
                    except ValueError:
                        window_start = now
                    if (now - window_start).total_seconds() > window_seconds:
                        count = 1
                        window_start = now
                    else:
                        count = int(row["failure_count"]) + 1
                locked_until = now + timedelta(seconds=lock_seconds) if count >= maximum else None
                conn.execute(
                    """INSERT INTO auth_failures(subject_hash,failure_count,window_started_at,locked_until,updated_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(subject_hash) DO UPDATE SET
                        failure_count=excluded.failure_count,
                        window_started_at=excluded.window_started_at,
                        locked_until=excluded.locked_until,
                        updated_at=excluded.updated_at""",
                    (
                        subject_hash,
                        count,
                        _utc_iso(window_start),
                        _utc_iso(locked_until) if locked_until else None,
                        now_iso,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise IdentityStoreError("auth_failure_state_write_failed") from exc

    def _clear_auth_failures(self, public_user_id: str) -> None:
        subject_hash = self._auth_subject_hash(public_user_id)
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute("DELETE FROM auth_failures WHERE subject_hash=?", (subject_hash,))
        except sqlite3.Error as exc:
            raise IdentityStoreError("auth_failure_state_clear_failed") from exc

    def authenticate_for_oauth(self, public_user_id: str, password: str) -> AccountRecord:
        if not public_user_id or not password or hmac.compare_digest(public_user_id, self.enrollment_id):
            raise OAuthRejected("authentication_rejected")
        subject_hash = self._auth_subject_hash(public_user_id)
        now = _utc_now()
        try:
            with closing(self._connect()) as conn:
                self._assert_not_locked(conn, subject_hash, now)
                row = conn.execute("SELECT * FROM users WHERE public_user_id=?", (public_user_id,)).fetchone()
        except OAuthRejected:
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("identity_read_failed") from exc
        if row is None or str(row["status"]) != "ACTIVE" or not self._verify_password_hash(
            password, str(row["password_hash"]) if row is not None else ""
        ):
            self._record_auth_failure(public_user_id, now)
            raise OAuthRejected("authentication_rejected")
        self._clear_auth_failures(public_user_id)
        return self._row_to_account(row)
