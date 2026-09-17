from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .memory import derive_secret_key


class VoiceAccessStoreError(RuntimeError):
    """Raised when Voice 1.1A durable state cannot be used safely."""


class VoiceAccessRejected(RuntimeError):
    """Raised when durable Voice 1.1A policy denies access."""


class VoiceRateLimitRejected(RuntimeError):
    """Raised with a bounded reason when Voice 1.1A admission is denied."""

    def __init__(self, reason_code: str, retry_after: int | None = None):
        self.reason_code = reason_code
        self.retry_after = retry_after
        super().__init__(reason_code)


@dataclass(frozen=True)
class VoiceAccessContext:
    user_uuid: str
    tenant_id: str
    entitlement_status: str


@dataclass(frozen=True)
class VoicePreferences:
    speech_rate: str = "normal"
    preserve_transcript: bool = False
    transcript_retention_seconds: int = 0

    def __post_init__(self) -> None:
        if self.speech_rate not in {"slower", "normal", "faster"}:
            raise ValueError("speech_rate_rejected")
        allowed_retention = {0, 900, 3600, 86400}
        if self.transcript_retention_seconds not in allowed_retention:
            raise ValueError("transcript_retention_rejected")
        if self.preserve_transcript != (self.transcript_retention_seconds > 0):
            raise ValueError("transcript_retention_mismatch")


@dataclass(frozen=True)
class VoiceUsageLimits:
    user_jobs_per_minute: int
    user_jobs_per_day: int
    user_characters_per_day: int
    tenant_jobs_per_minute: int
    tenant_jobs_per_day: int
    tenant_characters_per_day: int
    user_concurrency: int
    tenant_concurrency: int
    lease_seconds: int

    def __post_init__(self) -> None:
        if any(value <= 0 for value in self.__dict__.values()):
            raise ValueError("voice_usage_limits_must_be_positive")


@dataclass(frozen=True)
class VoiceUsageReservation:
    lease_id: str
    accepted_at: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(timezone.utc).isoformat()


def _window_start(value: datetime, kind: str) -> datetime:
    current = value.astimezone(timezone.utc)
    if kind == "MINUTE":
        return current.replace(second=0, microsecond=0)
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def _validated_uuid(value: str, reason: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise VoiceAccessRejected(reason) from exc
    canonical = str(parsed)
    if canonical != value.lower():
        raise VoiceAccessRejected(reason)
    return canonical


class VoiceAccessibilityStore:
    def __init__(
        self,
        db: Path,
        *,
        ownership_key: bytes,
        transcript_key: bytes,
    ):
        self.db = db
        self._ownership_key = ownership_key
        self._transcripts = AESGCM(transcript_key)
        self._initialize()

    @classmethod
    def from_env(cls, *, required: bool = True) -> VoiceAccessibilityStore | None:
        ownership_key = derive_secret_key("voice-1-1a-ownership", required=required)
        transcript_key = derive_secret_key("voice-1-1a-transcripts", required=required)
        if ownership_key is None or transcript_key is None:
            return None
        data_dir = Path(os.getenv("SARA_DATA_DIR", "./data")).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        return cls(
            data_dir / "sara_voice_accessibility.db",
            ownership_key=ownership_key,
            transcript_key=transcript_key,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        statements = (
            """CREATE TABLE IF NOT EXISTS voice_tenants(
                tenant_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS voice_memberships(
                user_uuid TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(tenant_id) REFERENCES voice_tenants(tenant_id)
            )""",
            """CREATE TABLE IF NOT EXISTS voice_entitlements(
                user_uuid TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                status TEXT NOT NULL,
                not_before TEXT NOT NULL,
                expires_at TEXT,
                granted_by_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_uuid) REFERENCES voice_memberships(user_uuid),
                FOREIGN KEY(tenant_id) REFERENCES voice_tenants(tenant_id)
            )""",
            """CREATE TABLE IF NOT EXISTS voice_preferences(
                user_uuid TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                speech_rate TEXT NOT NULL,
                preserve_transcript INTEGER NOT NULL,
                transcript_retention_seconds INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS voice_jobs(
                job_id TEXT PRIMARY KEY,
                user_uuid_hash TEXT NOT NULL,
                tenant_id_hash TEXT NOT NULL,
                source_response_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                preserve_transcript INTEGER NOT NULL,
                transcript_expires_at TEXT,
                receipt_envelope_digest TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                stopped_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS voice_transcripts(
                job_id TEXT PRIMARY KEY,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES voice_jobs(job_id)
            )""",
            """CREATE TABLE IF NOT EXISTS voice_usage_windows(
                subject_hash TEXT NOT NULL,
                subject_kind TEXT NOT NULL,
                window_kind TEXT NOT NULL,
                window_started_at TEXT NOT NULL,
                job_count INTEGER NOT NULL,
                character_count INTEGER NOT NULL,
                PRIMARY KEY(subject_hash,subject_kind,window_kind,window_started_at)
            )""",
            """CREATE TABLE IF NOT EXISTS voice_leases(
                lease_id TEXT PRIMARY KEY,
                user_uuid_hash TEXT NOT NULL,
                tenant_id_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS voice_access_audit(
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor_hash TEXT NOT NULL,
                tenant_id_hash TEXT,
                target_user_hash TEXT,
                reason_code TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
        )
        try:
            with closing(self._connect()) as conn:
                with conn:
                    for statement in statements:
                        conn.execute(statement)
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_access_store_initialization_failed") from exc
        try:
            os.chmod(self.db, 0o600)
        except OSError:
            pass

    def _hash(self, namespace: str, value: str) -> str:
        return hmac.new(
            self._ownership_key,
            f"{namespace}\0{value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _ownership(self, access: VoiceAccessContext) -> tuple[str, str]:
        return (
            self._hash("user", access.user_uuid),
            self._hash("tenant", access.tenant_id),
        )

    def _audit(
        self,
        conn: sqlite3.Connection,
        *,
        event_type: str,
        actor: str,
        reason_code: str,
        tenant_id: str | None = None,
        target_user: str | None = None,
    ) -> None:
        conn.execute(
            "INSERT INTO voice_access_audit VALUES(?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                event_type,
                self._hash("actor", actor),
                self._hash("tenant", tenant_id) if tenant_id else None,
                self._hash("user", target_user) if target_user else None,
                reason_code[:128],
                _utc_iso(),
            ),
        )

    def grant_entitlement(
        self,
        user_uuid: str,
        actor: str,
        expires_at: datetime | None = None,
    ) -> VoiceAccessContext:
        user_uuid = _validated_uuid(user_uuid, "user_identity_rejected")
        if not actor:
            raise VoiceAccessRejected("actor_required")
        now = _utc_now()
        now_iso = _utc_iso(now)
        expiry_iso = _utc_iso(expires_at) if expires_at is not None else None
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                membership = conn.execute(
                    "SELECT tenant_id FROM voice_memberships WHERE user_uuid=?",
                    (user_uuid,),
                ).fetchone()
                tenant_id = str(membership["tenant_id"]) if membership else str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO voice_tenants VALUES(?,?,?,?)
                    ON CONFLICT(tenant_id) DO UPDATE SET status='ACTIVE',updated_at=excluded.updated_at""",
                    (tenant_id, "ACTIVE", now_iso, now_iso),
                )
                conn.execute(
                    """INSERT INTO voice_memberships VALUES(?,?,?,?,?)
                    ON CONFLICT(user_uuid) DO UPDATE SET
                        tenant_id=excluded.tenant_id,status='ACTIVE',updated_at=excluded.updated_at""",
                    (user_uuid, tenant_id, "ACTIVE", now_iso, now_iso),
                )
                conn.execute(
                    """INSERT INTO voice_entitlements VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(user_uuid) DO UPDATE SET
                        tenant_id=excluded.tenant_id,status='ACTIVE',not_before=excluded.not_before,
                        expires_at=excluded.expires_at,granted_by_hash=excluded.granted_by_hash,
                        updated_at=excluded.updated_at""",
                    (
                        user_uuid,
                        tenant_id,
                        "ACTIVE",
                        now_iso,
                        expiry_iso,
                        self._hash("actor", actor),
                        now_iso,
                        now_iso,
                    ),
                )
                self._audit(
                    conn,
                    event_type="ENTITLEMENT_GRANTED",
                    actor=actor,
                    tenant_id=tenant_id,
                    target_user=user_uuid,
                    reason_code="owner_grant",
                )
                conn.commit()
        except VoiceAccessRejected:
            raise
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("entitlement_grant_failed") from exc
        return VoiceAccessContext(user_uuid, tenant_id, "ACTIVE")

    def revoke_entitlement(self, user_uuid: str, actor: str) -> None:
        user_uuid = _validated_uuid(user_uuid, "user_identity_rejected")
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT tenant_id FROM voice_entitlements WHERE user_uuid=?",
                    (user_uuid,),
                ).fetchone()
                if row is None:
                    raise VoiceAccessRejected("entitlement_not_found")
                tenant_id = str(row["tenant_id"])
                conn.execute(
                    "UPDATE voice_entitlements SET status='REVOKED',updated_at=? WHERE user_uuid=?",
                    (_utc_iso(), user_uuid),
                )
                self._audit(
                    conn,
                    event_type="ENTITLEMENT_REVOKED",
                    actor=actor,
                    tenant_id=tenant_id,
                    target_user=user_uuid,
                    reason_code="owner_revoke",
                )
                conn.commit()
        except VoiceAccessRejected:
            raise
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("entitlement_revoke_failed") from exc

    def entitlement_summary(self, user_uuid: str) -> dict[str, str | None]:
        user_uuid = _validated_uuid(user_uuid, "user_identity_rejected")
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT status,not_before,expires_at,created_at,updated_at FROM voice_entitlements WHERE user_uuid=?",
                    (user_uuid,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("entitlement_read_failed") from exc
        if row is None:
            raise VoiceAccessRejected("entitlement_not_found")
        return {
            "status": str(row["status"]),
            "not_before": str(row["not_before"]),
            "expires_at": str(row["expires_at"]) if row["expires_at"] is not None else None,
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def resolve_access(
        self,
        user_uuid: str,
        *,
        now: datetime | None = None,
    ) -> VoiceAccessContext:
        user_uuid = _validated_uuid(user_uuid, "user_identity_rejected")
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """SELECT e.tenant_id,e.status AS entitlement_status,e.not_before,e.expires_at,
                        m.status AS membership_status,t.status AS tenant_status
                    FROM voice_entitlements e
                    JOIN voice_memberships m ON m.user_uuid=e.user_uuid
                    JOIN voice_tenants t ON t.tenant_id=e.tenant_id
                    WHERE e.user_uuid=? AND m.tenant_id=e.tenant_id""",
                    (user_uuid,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("entitlement_read_failed") from exc
        if row is None:
            raise VoiceAccessRejected("entitlement_missing")
        if (
            str(row["entitlement_status"]) != "ACTIVE"
            or str(row["membership_status"]) != "ACTIVE"
            or str(row["tenant_status"]) != "ACTIVE"
        ):
            raise VoiceAccessRejected("entitlement_inactive")
        current = (now or _utc_now()).astimezone(timezone.utc)
        not_before = datetime.fromisoformat(str(row["not_before"]))
        if current < not_before:
            raise VoiceAccessRejected("entitlement_not_active")
        if row["expires_at"] is not None and current >= datetime.fromisoformat(str(row["expires_at"])):
            raise VoiceAccessRejected("entitlement_expired")
        return VoiceAccessContext(user_uuid, str(row["tenant_id"]), "ACTIVE")

    def get_preferences(self, access: VoiceAccessContext) -> VoicePreferences:
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT * FROM voice_preferences WHERE user_uuid=? AND tenant_id=?",
                    (access.user_uuid, access.tenant_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_preferences_read_failed") from exc
        if row is None:
            return VoicePreferences()
        return VoicePreferences(
            speech_rate=str(row["speech_rate"]),
            preserve_transcript=bool(row["preserve_transcript"]),
            transcript_retention_seconds=int(row["transcript_retention_seconds"]),
        )

    def set_preferences(
        self,
        access: VoiceAccessContext,
        preferences: VoicePreferences,
    ) -> VoicePreferences:
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """INSERT INTO voice_preferences VALUES(?,?,?,?,?,?)
                    ON CONFLICT(user_uuid) DO UPDATE SET
                        tenant_id=excluded.tenant_id,speech_rate=excluded.speech_rate,
                        preserve_transcript=excluded.preserve_transcript,
                        transcript_retention_seconds=excluded.transcript_retention_seconds,
                        updated_at=excluded.updated_at""",
                    (
                        access.user_uuid,
                        access.tenant_id,
                        preferences.speech_rate,
                        int(preferences.preserve_transcript),
                        preferences.transcript_retention_seconds,
                        _utc_iso(),
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_preferences_write_failed") from exc
        return preferences

    def record_job(
        self,
        job_id: str,
        access: VoiceAccessContext,
        source_digest: str,
        *,
        preserve_transcript: bool,
    ) -> None:
        if not job_id or len(source_digest) != 64:
            raise VoiceAccessRejected("voice_job_metadata_rejected")
        user_hash, tenant_hash = self._ownership(access)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """INSERT INTO voice_jobs(
                        job_id,user_uuid_hash,tenant_id_hash,source_response_sha256,status,
                        preserve_transcript,transcript_expires_at,receipt_envelope_digest,
                        created_at,completed_at,stopped_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        job_id,
                        user_hash,
                        tenant_hash,
                        source_digest,
                        "completed",
                        int(preserve_transcript),
                        None,
                        None,
                        _utc_iso(),
                        _utc_iso(),
                        None,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise VoiceAccessRejected("voice_job_conflict") from exc
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_job_write_failed") from exc

    def owns_job(self, job_id: str, access: VoiceAccessContext) -> bool:
        user_hash, tenant_hash = self._ownership(access)
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """SELECT 1 FROM voice_jobs
                    WHERE job_id=? AND user_uuid_hash=? AND tenant_id_hash=?""",
                    (job_id, user_hash, tenant_hash),
                ).fetchone()
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_job_read_failed") from exc
        return row is not None

    def record_receipt_envelope(
        self,
        job_id: str,
        access: VoiceAccessContext,
        receipt_ids: list[str],
    ) -> str:
        user_hash, tenant_hash = self._ownership(access)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """SELECT source_response_sha256 FROM voice_jobs
                    WHERE job_id=? AND user_uuid_hash=? AND tenant_id_hash=?""",
                    (job_id, user_hash, tenant_hash),
                ).fetchone()
                if row is None:
                    raise VoiceAccessRejected("job_not_owned")
                payload = {
                    "job_id": job_id,
                    "receipt_ids": list(receipt_ids),
                    "source_response_sha256": str(row["source_response_sha256"]),
                    "tenant_id_hash": tenant_hash,
                    "user_uuid_hash": user_hash,
                }
                digest = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                conn.execute(
                    "UPDATE voice_jobs SET receipt_envelope_digest=? WHERE job_id=?",
                    (digest, job_id),
                )
                conn.commit()
        except VoiceAccessRejected:
            raise
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_receipt_envelope_write_failed") from exc
        return digest

    def receipt_envelope_digest(
        self,
        job_id: str,
        access: VoiceAccessContext,
    ) -> str | None:
        user_hash, tenant_hash = self._ownership(access)
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """SELECT receipt_envelope_digest FROM voice_jobs
                    WHERE job_id=? AND user_uuid_hash=? AND tenant_id_hash=?""",
                    (job_id, user_hash, tenant_hash),
                ).fetchone()
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_receipt_envelope_read_failed") from exc
        if row is None:
            return None
        value = row["receipt_envelope_digest"]
        return str(value) if value is not None else None

    def mark_job_status(
        self,
        job_id: str,
        access: VoiceAccessContext,
        status: str,
        *,
        stopped: bool = False,
    ) -> None:
        if status not in {"pending", "running", "completed", "stopped", "failed"}:
            raise VoiceAccessRejected("voice_job_status_rejected")
        user_hash, tenant_hash = self._ownership(access)
        now_iso = _utc_iso()
        try:
            with closing(self._connect()) as conn:
                with conn:
                    cursor = conn.execute(
                        """UPDATE voice_jobs SET status=?,completed_at=?,
                            stopped_at=CASE WHEN ? THEN COALESCE(stopped_at,?) ELSE stopped_at END
                        WHERE job_id=? AND user_uuid_hash=? AND tenant_id_hash=?""",
                        (status, now_iso, int(stopped), now_iso, job_id, user_hash, tenant_hash),
                    )
                    if cursor.rowcount != 1:
                        raise VoiceAccessRejected("job_not_owned")
        except VoiceAccessRejected:
            raise
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_job_status_write_failed") from exc

    def save_transcript(
        self,
        job_id: str,
        access: VoiceAccessContext,
        text: str,
        expires_at: datetime,
    ) -> None:
        user_hash, tenant_hash = self._ownership(access)
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """SELECT preserve_transcript FROM voice_jobs
                    WHERE job_id=? AND user_uuid_hash=? AND tenant_id_hash=?""",
                    (job_id, user_hash, tenant_hash),
                ).fetchone()
                if row is None:
                    raise VoiceAccessRejected("job_not_owned")
                if not bool(row["preserve_transcript"]):
                    raise VoiceAccessRejected("transcript_preservation_disabled")
                nonce = os.urandom(12)
                aad = f"{job_id}\0{user_hash}\0{tenant_hash}".encode("utf-8")
                ciphertext = self._transcripts.encrypt(nonce, text.encode("utf-8"), aad)
                expiry_iso = _utc_iso(expires_at)
                conn.execute(
                    """INSERT INTO voice_transcripts VALUES(?,?,?,?,?)
                    ON CONFLICT(job_id) DO UPDATE SET nonce=excluded.nonce,
                        ciphertext=excluded.ciphertext,expires_at=excluded.expires_at,
                        created_at=excluded.created_at""",
                    (job_id, nonce, ciphertext, expiry_iso, _utc_iso()),
                )
                conn.execute(
                    "UPDATE voice_jobs SET transcript_expires_at=? WHERE job_id=?",
                    (expiry_iso, job_id),
                )
                conn.commit()
        except VoiceAccessRejected:
            raise
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_transcript_write_failed") from exc

    def load_transcript(
        self,
        job_id: str,
        access: VoiceAccessContext,
        *,
        now: datetime | None = None,
    ) -> str | None:
        user_hash, tenant_hash = self._ownership(access)
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """SELECT t.nonce,t.ciphertext,t.expires_at
                    FROM voice_transcripts t JOIN voice_jobs j ON j.job_id=t.job_id
                    WHERE t.job_id=? AND j.user_uuid_hash=? AND j.tenant_id_hash=?""",
                    (job_id, user_hash, tenant_hash),
                ).fetchone()
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_transcript_read_failed") from exc
        if row is None:
            return None
        current = (now or _utc_now()).astimezone(timezone.utc)
        if current >= datetime.fromisoformat(str(row["expires_at"])):
            return None
        aad = f"{job_id}\0{user_hash}\0{tenant_hash}".encode("utf-8")
        try:
            plaintext = self._transcripts.decrypt(bytes(row["nonce"]), bytes(row["ciphertext"]), aad)
        except Exception as exc:
            raise VoiceAccessStoreError("voice_transcript_authentication_failed") from exc
        return plaintext.decode("utf-8")

    def purge_user_data(self, user_uuid: str, actor: str) -> dict[str, int]:
        user_uuid = _validated_uuid(user_uuid, "user_identity_rejected")
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                membership = conn.execute(
                    "SELECT tenant_id FROM voice_memberships WHERE user_uuid=?",
                    (user_uuid,),
                ).fetchone()
                if membership is None:
                    raise VoiceAccessRejected("membership_not_found")
                tenant_id = str(membership["tenant_id"])
                user_hash = self._hash("user", user_uuid)
                tenant_hash = self._hash("tenant", tenant_id)
                job_ids = [
                    str(row["job_id"])
                    for row in conn.execute(
                        "SELECT job_id FROM voice_jobs WHERE user_uuid_hash=? AND tenant_id_hash=?",
                        (user_hash, tenant_hash),
                    ).fetchall()
                ]
                transcripts_deleted = 0
                if job_ids:
                    placeholders = ",".join("?" for _ in job_ids)
                    cursor = conn.execute(
                        f"DELETE FROM voice_transcripts WHERE job_id IN ({placeholders})",
                        job_ids,
                    )
                    transcripts_deleted = cursor.rowcount
                cursor = conn.execute(
                    "DELETE FROM voice_preferences WHERE user_uuid=? AND tenant_id=?",
                    (user_uuid, tenant_id),
                )
                preferences_deleted = cursor.rowcount
                self._audit(
                    conn,
                    event_type="USER_DATA_PURGED",
                    actor=actor,
                    tenant_id=tenant_id,
                    target_user=user_uuid,
                    reason_code="owner_purge",
                )
                conn.commit()
        except VoiceAccessRejected:
            raise
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_user_data_purge_failed") from exc
        return {
            "preferences_deleted": preferences_deleted,
            "transcripts_deleted": transcripts_deleted,
        }

    @staticmethod
    def _usage_row(
        conn: sqlite3.Connection,
        subject_hash: str,
        subject_kind: str,
        window_kind: str,
        window_started_at: str,
    ) -> tuple[int, int]:
        row = conn.execute(
            """SELECT job_count,character_count FROM voice_usage_windows
            WHERE subject_hash=? AND subject_kind=? AND window_kind=? AND window_started_at=?""",
            (subject_hash, subject_kind, window_kind, window_started_at),
        ).fetchone()
        if row is None:
            return 0, 0
        return int(row["job_count"]), int(row["character_count"])

    @staticmethod
    def _increment_usage(
        conn: sqlite3.Connection,
        subject_hash: str,
        subject_kind: str,
        window_kind: str,
        window_started_at: str,
        characters: int,
    ) -> None:
        conn.execute(
            """INSERT INTO voice_usage_windows(
                subject_hash,subject_kind,window_kind,window_started_at,job_count,character_count
            ) VALUES(?,?,?,?,1,?)
            ON CONFLICT(subject_hash,subject_kind,window_kind,window_started_at)
            DO UPDATE SET job_count=job_count+1,character_count=character_count+excluded.character_count""",
            (subject_hash, subject_kind, window_kind, window_started_at, characters),
        )

    def reserve_usage(
        self,
        access: VoiceAccessContext,
        *,
        characters: int,
        limits: VoiceUsageLimits,
        now: datetime | None = None,
    ) -> VoiceUsageReservation:
        if characters <= 0:
            raise VoiceRateLimitRejected("character_count_rejected")
        current = (now or _utc_now()).astimezone(timezone.utc)
        current_iso = _utc_iso(current)
        minute_start = _window_start(current, "MINUTE")
        day_start = _window_start(current, "DAY")
        minute_iso = _utc_iso(minute_start)
        day_iso = _utc_iso(day_start)
        minute_retry = max(1, int((minute_start + timedelta(minutes=1) - current).total_seconds()))
        day_retry = max(1, int((day_start + timedelta(days=1) - current).total_seconds()))
        user_hash, tenant_hash = self._ownership(access)
        lease_id = str(uuid.uuid4())
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM voice_leases WHERE expires_at<=?", (current_iso,))
                active_user = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM voice_leases WHERE user_uuid_hash=?",
                        (user_hash,),
                    ).fetchone()[0]
                )
                active_tenant = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM voice_leases WHERE tenant_id_hash=?",
                        (tenant_hash,),
                    ).fetchone()[0]
                )
                if active_user >= limits.user_concurrency:
                    raise VoiceRateLimitRejected("user_concurrency", limits.lease_seconds)
                if active_tenant >= limits.tenant_concurrency:
                    raise VoiceRateLimitRejected("tenant_concurrency", limits.lease_seconds)

                user_minute = self._usage_row(conn, user_hash, "USER", "MINUTE", minute_iso)
                user_day = self._usage_row(conn, user_hash, "USER", "DAY", day_iso)
                tenant_minute = self._usage_row(conn, tenant_hash, "TENANT", "MINUTE", minute_iso)
                tenant_day = self._usage_row(conn, tenant_hash, "TENANT", "DAY", day_iso)
                checks = (
                    (user_minute[0] + 1 > limits.user_jobs_per_minute, "user_jobs_per_minute", minute_retry),
                    (user_day[0] + 1 > limits.user_jobs_per_day, "user_jobs_per_day", day_retry),
                    (
                        user_day[1] + characters > limits.user_characters_per_day,
                        "user_characters_per_day",
                        day_retry,
                    ),
                    (
                        tenant_minute[0] + 1 > limits.tenant_jobs_per_minute,
                        "tenant_jobs_per_minute",
                        minute_retry,
                    ),
                    (tenant_day[0] + 1 > limits.tenant_jobs_per_day, "tenant_jobs_per_day", day_retry),
                    (
                        tenant_day[1] + characters > limits.tenant_characters_per_day,
                        "tenant_characters_per_day",
                        day_retry,
                    ),
                )
                for exceeded, reason_code, retry_after in checks:
                    if exceeded:
                        raise VoiceRateLimitRejected(reason_code, retry_after)

                for subject_hash, subject_kind in (
                    (user_hash, "USER"),
                    (tenant_hash, "TENANT"),
                ):
                    self._increment_usage(
                        conn,
                        subject_hash,
                        subject_kind,
                        "MINUTE",
                        minute_iso,
                        characters,
                    )
                    self._increment_usage(
                        conn,
                        subject_hash,
                        subject_kind,
                        "DAY",
                        day_iso,
                        characters,
                    )
                conn.execute(
                    "INSERT INTO voice_leases VALUES(?,?,?,?,?)",
                    (
                        lease_id,
                        user_hash,
                        tenant_hash,
                        _utc_iso(current + timedelta(seconds=limits.lease_seconds)),
                        current_iso,
                    ),
                )
                conn.commit()
        except VoiceRateLimitRejected:
            raise
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_usage_reservation_failed") from exc
        return VoiceUsageReservation(lease_id=lease_id, accepted_at=current_iso)

    def release_lease(self, lease_id: str) -> None:
        if not lease_id:
            return
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute("DELETE FROM voice_leases WHERE lease_id=?", (lease_id,))
        except sqlite3.Error as exc:
            raise VoiceAccessStoreError("voice_lease_release_failed") from exc
