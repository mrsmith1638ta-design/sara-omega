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


def derive_secret_key(context: str, *, required: bool = True) -> bytes | None:
    """Derive a domain-separated 32-byte secret from SARA's configured root key material."""
    material = _decode_key_material()
    if material is None:
        if required:
            raise MemoryKeyError("encrypted_memory_key_not_configured")
        return None
    normalized = context.strip()
    if not normalized or len(normalized) > 128:
        raise MemoryKeyError("invalid_secret_key_context")
    return hashlib.sha256(
        f"SARA-OMEGA:secret:{normalized}:v1\0".encode("utf-8") + material
    ).digest()


def _derive_memory_key(required: bool) -> bytes | None:
    material = _decode_key_material()
    if material is None:
        if required:
            raise MemoryKeyError("encrypted_memory_key_not_configured")
        return None
    # Keep the deployed conversation-memory key derivation stable for restart compatibility.
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

    def delete_json(self, scope: str, record_key: str) -> None:
        key_hash = self._key_hash(scope, record_key)
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        f"DELETE FROM {self.TABLE} WHERE scope=? AND record_key_hash=?",
                        (scope, key_hash),
                    )
        except sqlite3.Error as exc:
            raise MemoryStoreError("encrypted_state_delete_failed") from exc


class ConversationMemory:
    """Durable encrypted conversation history with restart and user continuity recovery."""

    SCOPE = "conversation-v1"
    USER_SCOPE = "conversation-user-v1"
    USER_INDEX_SCOPE = "conversation-user-index-v1"
    USER_CONTINUITY_SCOPE = "conversation-user-continuity-v1"

    def __init__(
        self,
        store: EncryptedStateStore,
        *,
        max_messages: int = 1000,
        continuity_max_items: int = 50,
    ):
        self.store = store
        self.max_messages = max(1, int(max_messages))
        self.continuity_max_items = max(1, int(continuity_max_items))

    @classmethod
    def from_env(cls, *, required: bool = True) -> "ConversationMemory | None":
        store = EncryptedStateStore.from_env(required=required)
        if store is None:
            return None
        max_messages = int(os.getenv("SARA_MEMORY_MAX_MESSAGES", "1000"))
        continuity_max_items = int(os.getenv("SARA_MEMORY_CONTINUITY_MAX_ITEMS", "50"))
        return cls(
            store,
            max_messages=max_messages,
            continuity_max_items=continuity_max_items,
        )

    @staticmethod
    def _validate_user_uuid(user_uuid: str) -> str:
        if not isinstance(user_uuid, str) or not user_uuid or len(user_uuid) > 64:
            raise MemoryStoreError("user_uuid_required")
        try:
            parsed = uuid.UUID(user_uuid)
        except (ValueError, AttributeError) as exc:
            raise MemoryStoreError("user_uuid_invalid") from exc
        canonical = str(parsed)
        if canonical != user_uuid.lower():
            raise MemoryStoreError("user_uuid_invalid")
        return canonical

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
            raise MemoryStoreError("session_id_required")
        return session_id

    @staticmethod
    def _validate_messages(value: Any) -> list[dict[str, str]]:
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

    def save(self, session_id: str, messages: list[dict[str, str]]) -> None:
        if not session_id:
            raise MemoryStoreError("session_id_required")
        bounded = self._validate_messages(messages)[-self.max_messages :]
        self.store.save_json(self.SCOPE, session_id, bounded)

    def load(self, session_id: str) -> list[dict[str, str]]:
        if not session_id:
            raise MemoryStoreError("session_id_required")
        value = self.store.load_json(self.SCOPE, session_id)
        if value is None:
            return []
        return self._validate_messages(value)

    @staticmethod
    def _thread_key(user_uuid: str, session_id: str) -> str:
        return f"{user_uuid}\0{session_id}"

    @staticmethod
    def _user_key(user_uuid: str) -> str:
        return f"{user_uuid}\0state"

    def _load_thread_index(self, user_uuid: str) -> list[str]:
        raw = self.store.load_json(self.USER_INDEX_SCOPE, self._user_key(user_uuid))
        if raw is None:
            return []
        if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw):
            raise MemoryStoreError("conversation_user_index_schema_invalid")
        return raw[-self.continuity_max_items :]

    def _save_thread_index(self, user_uuid: str, session_ids: list[str]) -> list[str]:
        unique: list[str] = []
        for session_id in session_ids:
            if session_id in unique:
                unique.remove(session_id)
            unique.append(session_id)
        evicted = unique[:-self.continuity_max_items]
        bounded = unique[-self.continuity_max_items :]
        self.store.save_json(self.USER_INDEX_SCOPE, self._user_key(user_uuid), bounded)
        for session_id in evicted:
            self.store.delete_json(self.USER_SCOPE, self._thread_key(user_uuid, session_id))
        return bounded

    def save_for_user(
        self,
        user_uuid: str,
        session_id: str,
        messages: list[dict[str, str]],
    ) -> None:
        user_uuid = self._validate_user_uuid(user_uuid)
        session_id = self._validate_session_id(session_id)
        bounded = self._validate_messages(messages)[-self.max_messages :]
        self.store.save_json(self.USER_SCOPE, self._thread_key(user_uuid, session_id), bounded)
        index = self._load_thread_index(user_uuid)
        self._save_thread_index(user_uuid, [*index, session_id])

    def load_for_user(self, user_uuid: str, session_id: str) -> list[dict[str, str]]:
        user_uuid = self._validate_user_uuid(user_uuid)
        session_id = self._validate_session_id(session_id)
        value = self.store.load_json(self.USER_SCOPE, self._thread_key(user_uuid, session_id))
        if value is None:
            return []
        return self._validate_messages(value)

    def list_user_threads(self, user_uuid: str, limit: int = 20) -> list[dict[str, str]]:
        user_uuid = self._validate_user_uuid(user_uuid)
        bounded_limit = max(1, min(int(limit), self.continuity_max_items))
        index = self._load_thread_index(user_uuid)[-bounded_limit:]
        return [{"session_id": session_id} for session_id in index]

    def load_user_continuity(self, user_uuid: str) -> dict[str, Any]:
        user_uuid = self._validate_user_uuid(user_uuid)
        raw = self.store.load_json(self.USER_CONTINUITY_SCOPE, self._user_key(user_uuid))
        if raw is None:
            return {"thread_count": 0, "threads": []}
        if not isinstance(raw, dict):
            raise MemoryStoreError("conversation_user_continuity_schema_invalid")
        threads = raw.get("threads")
        if not isinstance(threads, list):
            raise MemoryStoreError("conversation_user_continuity_schema_invalid")
        validated: list[dict[str, Any]] = []
        for item in threads[-self.continuity_max_items :]:
            if not isinstance(item, dict):
                raise MemoryStoreError("conversation_user_continuity_schema_invalid")
            session_id = item.get("session_id")
            messages = item.get("messages")
            if not isinstance(session_id, str) or not isinstance(messages, list):
                raise MemoryStoreError("conversation_user_continuity_schema_invalid")
            validated_messages = self._validate_messages(messages)
            validated.append({"session_id": session_id, "messages": validated_messages})
        return {"thread_count": len(validated), "threads": validated}

    def update_user_continuity(
        self,
        user_uuid: str,
        *,
        session_id: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        user_uuid = self._validate_user_uuid(user_uuid)
        session_id = self._validate_session_id(session_id)
        validated_messages = self._validate_messages(messages)
        index = self._save_thread_index(user_uuid, [*self._load_thread_index(user_uuid), session_id])
        previous = self.load_user_continuity(user_uuid)
        by_session = {
            str(item["session_id"]): item
            for item in previous.get("threads", [])
            if isinstance(item, dict) and isinstance(item.get("session_id"), str)
        }
        # Continuity is deterministic and bounded: retain only recent transcript snippets.
        snippets = [
            {"role": item["role"], "content": item["content"][:500]}
            for item in validated_messages[-6:]
        ]
        by_session[session_id] = {"session_id": session_id, "messages": snippets}
        threads = [by_session[item] for item in index if item in by_session]
        continuity = {"thread_count": len(threads), "threads": threads}
        self.store.save_json(self.USER_CONTINUITY_SCOPE, self._user_key(user_uuid), continuity)
        return continuity

    def forget_user(self, user_uuid: str) -> None:
        user_uuid = self._validate_user_uuid(user_uuid)
        index = self._load_thread_index(user_uuid)
        for session_id in index:
            self.store.delete_json(self.USER_SCOPE, self._thread_key(user_uuid, session_id))
        self.store.delete_json(self.USER_INDEX_SCOPE, self._user_key(user_uuid))
        self.store.delete_json(self.USER_CONTINUITY_SCOPE, self._user_key(user_uuid))


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
