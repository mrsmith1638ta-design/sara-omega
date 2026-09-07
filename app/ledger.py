from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import IntegrityStatus
from .signing import DualSigner, SigningError

SCHEMA_VERSION = "omega-verdict-ledger-v1"
GENESIS_HASH = "0" * 128


class OmegaLedgerError(RuntimeError):
    pass


def canonicalize(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


class OmegaVerdictLedger:
    def __init__(self, db: str | Path, signer: DualSigner):
        self.db = Path(db)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.signer = signer
        self._append_lock = asyncio.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS omega_verdict_ledger(
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        decision_id TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        schema_version TEXT NOT NULL,
                        previous_record_hash TEXT NOT NULL,
                        current_record_hash TEXT NOT NULL UNIQUE,
                        canonical_payload TEXT NOT NULL,
                        ed25519_json TEXT NOT NULL,
                        ml_dsa_json TEXT NOT NULL,
                        supersedes_decision_id TEXT NULL
                    )"""
                )
                conn.execute(
                    """CREATE TRIGGER IF NOT EXISTS omega_verdict_ledger_no_update
                    BEFORE UPDATE ON omega_verdict_ledger
                    BEGIN
                        SELECT RAISE(ABORT, 'omega_ledger_append_only');
                    END"""
                )
                conn.execute(
                    """CREATE TRIGGER IF NOT EXISTS omega_verdict_ledger_no_delete
                    BEFORE DELETE ON omega_verdict_ledger
                    BEGIN
                        SELECT RAISE(ABORT, 'omega_ledger_append_only');
                    END"""
                )

    @staticmethod
    def _core(
        decision_id: str,
        timestamp: str,
        previous_hash: str,
        payload: Any,
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision_id": decision_id,
            "timestamp": timestamp,
            "previous_record_hash": previous_hash,
            "payload": payload,
        }

    def _head_from_conn(self, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT current_record_hash FROM omega_verdict_ledger ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return str(row[0]) if row else GENESIS_HASH

    def chain_head(self) -> str:
        with closing(self._connect()) as conn:
            return self._head_from_conn(conn)

    def count(self) -> int:
        with closing(self._connect()) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM omega_verdict_ledger").fetchone()[0])

    def get(self, decision_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM omega_verdict_ledger WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        return dict(row) if row else None

    def verify_chain(self) -> bool:
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    "SELECT * FROM omega_verdict_ledger ORDER BY sequence ASC"
                ).fetchall()
            expected_previous = GENESIS_HASH
            for row in rows:
                if str(row["previous_record_hash"]) != expected_previous:
                    return False
                if str(row["schema_version"]) != SCHEMA_VERSION:
                    return False
                ed = json.loads(str(row["ed25519_json"]))
                ml = json.loads(str(row["ml_dsa_json"]))
                if str(ed.get("algorithm", "")).lower() != "ed25519" or not bool(ed.get("verified")):
                    return False
                if str(ml.get("algorithm", "")).lower().replace("_", "-") != "ml-dsa" or not bool(ml.get("verified")):
                    return False
                payload = json.loads(str(row["canonical_payload"]))
                core = self._core(
                    str(row["decision_id"]),
                    str(row["created_at"]),
                    str(row["previous_record_hash"]),
                    payload,
                )
                digest_hex = hashlib.sha512(canonicalize(core)).hexdigest()
                if digest_hex != str(row["current_record_hash"]):
                    return False
                expected_previous = digest_hex
            return True
        except Exception:
            return False

    async def append(
        self,
        decision_id: str,
        payload: dict[str, Any],
        *,
        timestamp: str | None = None,
        supersedes_decision_id: str | None = None,
    ) -> IntegrityStatus:
        if not decision_id:
            raise OmegaLedgerError("decision_id_required")
        timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        async with self._append_lock:
            if not self.verify_chain():
                raise OmegaLedgerError("chain_invalid")
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                previous_hash = self._head_from_conn(conn)
                if supersedes_decision_id:
                    parent = conn.execute(
                        "SELECT 1 FROM omega_verdict_ledger WHERE decision_id=?",
                        (supersedes_decision_id,),
                    ).fetchone()
                    if parent is None:
                        raise OmegaLedgerError("supersedes_decision_not_found")
                core = self._core(decision_id, timestamp, previous_hash, payload)
                canonical_core = canonicalize(core)
                digest = hashlib.sha512(canonical_core).digest()
                current_hash = digest.hex()
                try:
                    ed25519, ml_dsa = await self.signer.sign_and_verify(digest)
                except SigningError as exc:
                    raise OmegaLedgerError(f"signing_failed:{exc}") from None
                canonical_payload = canonicalize(payload).decode("utf-8")
                conn.execute(
                    """INSERT INTO omega_verdict_ledger(
                        decision_id,created_at,schema_version,previous_record_hash,
                        current_record_hash,canonical_payload,ed25519_json,ml_dsa_json,
                        supersedes_decision_id
                    ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        decision_id,
                        timestamp,
                        SCHEMA_VERSION,
                        previous_hash,
                        current_hash,
                        canonical_payload,
                        json.dumps(ed25519.model_dump(), sort_keys=True, separators=(",", ":")),
                        json.dumps(ml_dsa.model_dump(), sort_keys=True, separators=(",", ":")),
                        supersedes_decision_id,
                    ),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
            finally:
                conn.close()

            row = self.get(decision_id)
            if row is None:
                raise OmegaLedgerError("SUBMISSION_UNVERIFIED:read_after_write_missing")
            if row["current_record_hash"] != current_hash or row["previous_record_hash"] != previous_hash:
                raise OmegaLedgerError("SUBMISSION_UNVERIFIED:read_after_write_mismatch")
            if self.chain_head() != current_hash or not self.verify_chain():
                raise OmegaLedgerError("SUBMISSION_UNVERIFIED:chain_head_confirmation_failed")
            return IntegrityStatus(
                schema_version=SCHEMA_VERSION,
                previous_record_hash=previous_hash,
                current_record_hash=current_hash,
                chain_valid=True,
                ed25519=ed25519,
                ml_dsa=ml_dsa,
                durable=True,
                read_after_write_verified=True,
                status="DURABLE",
            )
