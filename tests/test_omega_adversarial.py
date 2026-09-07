import json
import sqlite3

import pytest

from app.ledger import OmegaLedgerError
from app.models import (
    Claim,
    Disposition,
    GovernanceDecision,
    Problem,
    SignatureRecord,
    SpecialistResult,
    VerificationStatus,
)
from app.orchestrator import SaraOmega
from tests.test_omega_ledger import FakeSigner, make_ledger


@pytest.mark.asyncio
async def test_forged_previous_hash_breaks_chain(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    await ledger.append("d1", {"v": 1})
    with sqlite3.connect(ledger.db) as conn:
        conn.execute("DROP TRIGGER omega_verdict_ledger_no_update")
        conn.execute("UPDATE omega_verdict_ledger SET previous_record_hash=? WHERE decision_id='d1'", ("f" * 128,))
        conn.commit()
    assert ledger.verify_chain() is False


@pytest.mark.asyncio
async def test_duplicate_decision_id_is_rejected(tmp_path):
    ledger, _, _ = make_ledger(tmp_path)
    await ledger.append("d1", {"v": 1})
    with pytest.raises(sqlite3.IntegrityError):
        await ledger.append("d1", {"v": 2})
    assert ledger.count() == 1


@pytest.mark.asyncio
async def test_same_signature_reused_for_different_digest_fails_verification(tmp_path):
    class DigestBoundSigner(FakeSigner):
        def __init__(self, algorithm):
            super().__init__(algorithm)
            self.first = None
        async def sign(self, digest):
            if self.first is None:
                self.first = digest
            return SignatureRecord(algorithm=self.algorithm, key_id=self.algorithm, signature_b64="same", signer="fake")
        async def verify(self, digest, signature):
            return digest == self.first
    ed = DigestBoundSigner("Ed25519")
    ml = DigestBoundSigner("ML-DSA")
    ledger, _, _ = make_ledger(tmp_path, ed=ed, ml=ml)
    await ledger.append("d1", {"v": 1})
    with pytest.raises(OmegaLedgerError, match="signing_failed"):
        await ledger.append("d2", {"v": 2})


@pytest.mark.asyncio
async def test_signer_uncertainty_is_non_durable_and_not_retried():
    class Governance:
        def evaluate(self, p): return GovernanceDecision(disposition=Disposition.ALLOW)
    class Authority:
        def authorize(self, p, g): return g
    class Judge:
        async def synthesize(self, payload):
            return {"decision":"ANSWER","why":"x","confidence":0.7,"council_findings":[],"critical_assumption":None,"primary_risk":None,"evidence_gaps":[],"next_action":"none"}
    class History:
        def recent(self, n): return []
    class UncertainLedger:
        def __init__(self): self.calls = 0
        async def append(self, *args, **kwargs):
            self.calls += 1
            raise OmegaLedgerError("SUBMISSION_UNVERIFIED:timeout_after_submission")
    uncertain = UncertainLedger()
    sara = SaraOmega(governance=Governance(), authority=Authority(), judge=Judge(), history_ledger=History(), signed_ledger=uncertain, providers={})
    verdict = await sara.solve(Problem(query="Explain a triangle", council=False))
    assert uncertain.calls == 1
    assert verdict.integrity.durable is False
    assert verdict.decision_id is None


def test_provider_consensus_without_evidence_is_not_verified():
    from app.verification import EvidenceVerifier
    verifier = EvidenceVerifier()
    a = Claim(provider="a", statement="same")
    b = Claim(provider="b", statement="same")
    claims = verifier.verify([
        SpecialistResult(provider="a", role="r", task="q", claims=[a]),
        SpecialistResult(provider="b", role="r", task="q", claims=[b]),
    ])
    assert all(c.verification == VerificationStatus.UNSUPPORTED for c in claims)


def test_serialized_integrity_objects_do_not_contain_private_key_or_tokens():
    record = SignatureRecord(algorithm="Ed25519", key_id="public", signature_b64="c2ln", verified=True)
    serialized = json.dumps(record.model_dump()).lower()
    assert "private_key" not in serialized
    assert "signer_token" not in serialized
