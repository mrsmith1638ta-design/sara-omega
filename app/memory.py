from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .models import Problem, Verdict


class MemoryKeyError(RuntimeError):
    """Raised when encrypted persistence is required but no valid key is configured."""


class MemoryStoreError(RuntimeError):
    """Raised when encrypted state cannot be safely read or written."""


def _data_dir() -> Path:
    data_dir = Path(os.getenv("SARA_DATA_DIR", "./data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(data_dir, 0o700)
    except OSError:
        pass
    return data_dir


def _decode_key_material() -> bytes | None:
    candidates = (
        ("SARA_MEMORY_KEY_HEX", "hex"),
        ("SARA_MEMORY_KEY_B64", "b64"),
        ("SARA_FAILSAFE_MASTER_KEY_HEX", "hex"),
        ("SARA_FAILSAFE_MASTER_KEY_B64", "b64"),
    )
    for name, encoding in candidates:
        raw = os.getenv(name, "").strip()
        if not raw:
            continue
        try:
            material = bytes.fromhex(raw) if encoding == "hex" else base64.b64decode(raw, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise MemoryKeyError(f"invalid_encryption_key_encoding:{name}") from exc
        if len(material) < 32:
            raise MemoryKeyError(f"encryption_key_too_short:{name}")
        return material
    return None


def _derive_memory_key(required: bool) -> bytes | None:
    material = _decode_key_material()
    if material is None:
        if required:
            raise MemoryKeyError("encrypted_memory_key_not_configured")
        return None
    # Domain-separate memory encryption even when the fail-safe master key is reused.
    return hashlib.sha256(b"SARA-OMEGA:encrypted-memory:v1\0" + material).digest()


class EncryptedStateStore:
    """Small AES-GCM JSON store backed by SARA_DATA_DIR/sara_omega.db."""

    TABLE = "encrypted_state"

    def __init__(self, db: Path, key: bytes):
        self.db = db
        self._aesgcm = AESGCM(key)
        self._initialize()

    @classmethod
    def from_env(cls, *, required: bool = True) -> "EncryptedStateStore | None":
        key = _derive_memory_key(required)
        if key is None:
            return None
        return cls(_data_dir() / "sara_omega.db", key)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=10.0)
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS {self.TABLE}(
                        scope TEXT NOT NULL,
                        record_key_hash TEXT NOT NULL,
                        nonce BLOB NOT NULL,
                        ciphertext BLOB NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(scope, record_key_hash)
                    )"""
                )
        try:
            os.chmod(self.db, 0o600)
        except OSError:
            pass

    @staticmethod
    def _key_hash(scope: str, record_key: str) -> str:
        return hashlib.sha256(f"{scope}\0{record_key}".encode("utf-8")).hexdigest()

    def save_json(self, scope: str, record_key: str, payload: Any) -> None:
        key_hash = self._key_hash(scope, record_key)
        aad = f"{scope}\0{key_hash}".encode("utf-8")
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, aad)
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        f"""INSERT INTO {self.TABLE}(scope,record_key_hash,nonce,ciphertext,updated_at)
                        VALUES(?,?,?,?,?)
                        ON CONFLICT(scope,record_key_hash) DO UPDATE SET
                            nonce=excluded.nonce,
                            ciphertext=excluded.ciphertext,
                            updated_at=excluded.updated_at""",
                        (scope, key_hash, nonce, ciphertext, datetime.now(timezone.utc).isoformat()),
                    )
        except sqlite3.Error as exc:
            raise MemoryStoreError("encrypted_state_write_failed") from exc

    def load_json(self, scope: str, record_key: str) -> Any | None:
        key_hash = self._key_hash(scope, record_key)
        aad = f"{scope}\0{key_hash}".encode("utf-8")
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    f"SELECT nonce,ciphertext FROM {self.TABLE} WHERE scope=? AND record_key_hash=?",
                    (scope, key_hash),
                ).fetchone()
        except sqlite3.Error as exc:
            raise MemoryStoreError("encrypted_state_read_failed") from exc
        if row is None:
            return None
        try:
            plaintext = self._aesgcm.decrypt(bytes(row[0]), bytes(row[1]), aad)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            raise MemoryStoreError("encrypted_state_authentication_failed") from exc


class ConversationMemory:
    """Durable encrypted conversation history with restart recovery."""

    SCOPE = "conversation-v1"

    def __init__(self, store: EncryptedStateStore, *, max_messages: int = 1000):
        self.store = store
        self.max_messages = max(1, int(max_messages))

    @classmethod
    def from_env(cls, *, required: bool = True) -> "ConversationMemory | None":
        store = EncryptedStateStore.from_env(required=required)
        if store is None:
            return None
        max_messages = int(os.getenv("SARA_MEMORY_MAX_MESSAGES", "1000"))
        return cls(store, max_messages=max_messages)

    def save(self, session_id: str, messages: list[dict[str, str]]) -> None:
        if not session_id:
            raise MemoryStoreError("session_id_required")
        bounded = messages[-self.max_messages :]
        self.store.save_json(self.SCOPE, session_id, bounded)

    def load(self, session_id: str) -> list[dict[str, str]]:
        if not session_id:
            raise MemoryStoreError("session_id_required")
        value = self.store.load_json(self.SCOPE, session_id)
        if value is None:
            return []
        if not isinstance(value, list):
            raise MemoryStoreError("conversation_schema_invalid")
        messages: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                raise MemoryStoreError("conversation_schema_invalid")
            role = item.get("role")
            content = item.get("content")
            if not isinstance(role, str) or not isinstance(content, str):
                raise MemoryStoreError("conversation_schema_invalid")
            messages.append({"role": role, "content": content})
        return messages


class DecisionLedger:
    def __init__(self):
        data_dir = _data_dir()
        self.db = data_dir / "sara_omega.db"
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                c.execute('''CREATE TABLE IF NOT EXISTS decisions(
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, query TEXT NOT NULL,
                    problem_json TEXT NOT NULL, verdict_json TEXT NOT NULL,
                    outcome_json TEXT, lesson TEXT)''')

    def record(self, p: Problem, v: Verdict) -> str:
        did = str(uuid.uuid4())
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                c.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?)", (
                    did, datetime.now(timezone.utc).isoformat(), p.query,
                    p.model_dump_json(), v.model_dump_json(), None, None))
        return did

    def record_outcome(self, decision_id: str, outcome: dict, lesson: str | None = None):
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                c.execute("UPDATE decisions SET outcome_json=?, lesson=? WHERE id=?",
                          (json.dumps(outcome), lesson, decision_id))

    def recent(self, limit: int = 10) -> list[dict]:
        with closing(sqlite3.connect(self.db)) as c:
            rows = c.execute("SELECT id,created_at,query,verdict_json,outcome_json,lesson FROM decisions ORDER BY created_at DESC LIMIT ?",
                             (limit,)).fetchall()
        return [{"id":r[0],"created_at":r[1],"query":r[2],"verdict":json.loads(r[3]),
                 "outcome":json.loads(r[4]) if r[4] else None,"lesson":r[5]} for r in rows]
