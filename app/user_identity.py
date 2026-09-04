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


class UserIdentityStore:
    """Durable SARA account and single-use enrollment store."""

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

    def _token_hash(self, token: str) -> str:
        return hmac.new(self._token_hash_key, token.encode("utf-8"), hashlib.sha256).hexdigest()

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
        ttl = int(
            ttl_seconds
            if ttl_seconds is not None
            else os.getenv("SARA_INVITE_TTL_SECONDS", "86400")
        )
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
                    """UPDATE enrollment_invites
                    SET consumed_at=?,user_uuid=?
                    WHERE token_hash=? AND consumed_at IS NULL""",
                    (now_iso, account.user_uuid, token_hash),
                )
                if updated.rowcount != 1:
                    conn.rollback()
                    raise EnrollmentRejected("invitation_not_available")
                conn.commit()
                return account
        except (EnrollmentRejected, PasswordPolicyRejected, IdentityStoreError):
            raise
        except sqlite3.Error as exc:
            raise IdentityStoreError("enrollment_write_failed") from exc

    def authenticate_password(self, public_user_id: str, password: str) -> AccountRecord:
        if not public_user_id or not password:
            raise EnrollmentRejected("authentication_rejected")
        if hmac.compare_digest(public_user_id, self.enrollment_id):
            raise EnrollmentRejected("authentication_rejected")
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT * FROM users WHERE public_user_id=?",
                    (public_user_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise IdentityStoreError("identity_read_failed") from exc
        if row is None or str(row["status"]) != "ACTIVE":
            raise EnrollmentRejected("authentication_rejected")
        if not self._verify_password_hash(password, str(row["password_hash"])):
            raise EnrollmentRejected("authentication_rejected")
        return self._row_to_account(row)
