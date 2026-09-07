import asyncio
import json
import sqlite3

import pytest

from app.ledger import GENESIS_HASH, OmegaLedgerError, OmegaVerdictLedger, canonicalize
from app.models import SignatureRecord
from app.signing import DualSigner, SigningError


class FakeSigner:
    def __init__(self, algorithm, *, verified=True, fail=False):
        self.algorithm = algorithm
        self.verified = verified
        self.fail = fail
        self.seen = []

    async def sign(self, digest):
        self.seen.append(digest)
        if self.fail:
            raise SigningError("signer_unavailable")
        return SignatureRecord(algorithm=self.algorithm, key_id=self.algorithm, signature_b64="c2ln", signer="fake")

    async def verify(self, digest, signature):
        self.seen.append(digest)
        return self.verified


def make_ledger(tmp_path, *, ed=None, ml=None):
    ed = ed or FakeSigner("Ed25519")
    ml = ml or FakeSigner("ML-DSA")
    return OmegaVerdictLedger(tmp_path / "omega.db", DualSigner(ed, ml)), ed, ml


def test_canonicalization_is_deterministic():
    assert canonicalize({"b": 2, "a": 1}) == canonicalize({"a": 1, "b": 2})


@pytest.mark.asyncio
async def test_genesis_and_second_record_chain(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    first = await ledger.append("d1", {"verdict": "one"}, timestamp="2026-09-07T00:00:00+00:00")
    second = await ledger.append("d2", {"verdict": "two"}, timestamp="2026-09-07T00:00:01+00:00")
    assert first.previous_record_hash == GENESIS_HASH
    assert second.previous_record_hash == first.current_record_hash
    assert second.durable is True
    assert ledger.verify_chain() is True


@pytest.mark.asyncio
async def test_both_signers_receive_same_digest(tmp_path):
    ledger, ed, ml = make_ledger(tmp_path)
    await ledger.append("d1", {"v": 1}, timestamp="2026-09-07T00:00:00+00:00")
    assert ed.seen[0] == ml.seen[0]
    assert ed.seen[1] == ml.seen[1]


@pytest.mark.asyncio
async def test_no_row_when_either_signer_fails(tmp_path):
    ledger, _, _ = make_ledger(tmp_path, ml=FakeSigner("ML-DSA", fail=True))
    with pytest.raises(OmegaLedgerError, match="signing_failed"):
        await ledger.append("d1", {"v": 1})
    assert ledger.count() == 0


@pytest.mark.asyncio
async def test_accepted_rows_are_immutable(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    await ledger.append("d1", {"v": 1})
    with sqlite3.connect(ledger.db) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="omega_ledger_append_only"):
            conn.execute("UPDATE omega_verdict_ledger SET canonical_payload='{}' WHERE decision_id='d1'")
        with pytest.raises(sqlite3.DatabaseError, match="omega_ledger_append_only"):
            conn.execute("DELETE FROM omega_verdict_ledger WHERE decision_id='d1'")


@pytest.mark.asyncio
async def test_supersession_does_not_modify_prior_record(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    first = await ledger.append("d1", {"v": 1})
    await ledger.append("d2", {"v": 2}, supersedes_decision_id="d1")
    row = ledger.get("d1")
    assert row["current_record_hash"] == first.current_record_hash
    assert ledger.get("d2")["supersedes_decision_id"] == "d1"


@pytest.mark.asyncio
async def test_restart_reconstructs_and_verifies_chain_head(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    first = await ledger.append("d1", {"v": 1})
    restarted, _, _ = make_ledger(tmp_path)
    assert restarted.verify_chain() is True
    assert restarted.chain_head() == first.current_record_hash


@pytest.mark.asyncio
async def test_tampering_is_detected(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    await ledger.append("d1", {"v": 1})
    with sqlite3.connect(ledger.db) as conn:
        conn.execute("DROP TRIGGER omega_verdict_ledger_no_update")
        conn.execute("UPDATE omega_verdict_ledger SET canonical_payload=? WHERE decision_id='d1'", (json.dumps({"v": 999}),))
        conn.commit()
    assert ledger.verify_chain() is False


@pytest.mark.asyncio
async def test_concurrent_appends_serialize(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    await asyncio.gather(*[
        ledger.append(f"d{i}", {"v": i}) for i in range(8)
    ])
    assert ledger.count() == 8
    assert ledger.verify_chain() is True


@pytest.mark.asyncio
async def test_swapped_signature_metadata_breaks_chain_verification(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    await ledger.append("d1", {"v": 1})
    row = ledger.get("d1")
    with sqlite3.connect(ledger.db) as conn:
        conn.execute("DROP TRIGGER omega_verdict_ledger_no_update")
        conn.execute(
            "UPDATE omega_verdict_ledger SET ed25519_json=?, ml_dsa_json=? WHERE decision_id='d1'",
            (row["ml_dsa_json"], row["ed25519_json"]),
        )
        conn.commit()
    assert ledger.verify_chain() is False
