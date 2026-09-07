import pytest

from app.models import (
    CouncilStage,
    Disposition,
    GovernanceDecision,
    IntegrityStatus,
    Problem,
    SignatureRecord,
    SpecialistResult,
)
from app.orchestrator import SaraOmega
from app.ledger import OmegaLedgerError


class FakeGovernance:
    def __init__(self, disposition=Disposition.ALLOW): self.disposition = disposition
    def evaluate(self, problem): return GovernanceDecision(disposition=self.disposition)

class FakeAuthority:
    def authorize(self, problem, governance): return governance

class FakeJudge:
    async def synthesize(self, payload):
        return {"decision":"ANSWER", "why":"synthesized", "confidence":0.8,
                "council_findings":[], "critical_assumption":None,
                "primary_risk":None, "evidence_gaps":[], "next_action":"none"}

class FakeProvider:
    def __init__(self, name): self.name=name; self.calls=0
    async def run(self, assignment):
        self.calls += 1
        return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task)

class FakeSignedLedger:
    def __init__(self, fail=False): self.fail=fail; self.payloads=[]
    async def append(self, decision_id, payload, **kwargs):
        self.payloads.append(payload)
        if self.fail: raise OmegaLedgerError("signing_failed:signer_unavailable")
        sig1=SignatureRecord(algorithm="Ed25519",key_id="e",signature_b64="c2ln",verified=True)
        sig2=SignatureRecord(algorithm="ML-DSA",key_id="m",signature_b64="c2ln",verified=True)
        return IntegrityStatus(previous_record_hash="0"*128,current_record_hash="1"*128,chain_valid=True,
                               ed25519=sig1,ml_dsa=sig2,durable=True,read_after_write_verified=True,status="DURABLE")

class FakeHistory:
    def recent(self, limit): return []


def build(*, governance=None, signed_ledger=None):
    providers={name: FakeProvider(name) for name in ("perplexity","codex","cursor","data_analytics")}
    sara=SaraOmega(
        governance=governance or FakeGovernance(), authority=FakeAuthority(), judge=FakeJudge(),
        providers=providers, history_ledger=FakeHistory(), signed_ledger=signed_ledger or FakeSignedLedger())
    return sara,providers


@pytest.mark.asyncio
async def test_every_request_traverses_all_internal_council_stages():
    sara,_=build()
    verdict=await sara.solve(Problem(query="Explain a triangle"))
    assert verdict.council_trace.completed == list(CouncilStage)

@pytest.mark.asyncio
async def test_council_false_still_traverses_all_stages():
    sara,_=build()
    verdict=await sara.solve(Problem(query="Explain a triangle", council=False))
    assert verdict.council_trace.completed == list(CouncilStage)

@pytest.mark.asyncio
async def test_trivial_request_uses_zero_external_specialists_but_full_council():
    sara,providers=build()
    verdict=await sara.solve(Problem(query="Explain what a triangle is"))
    assert verdict.providers_used == []
    assert sum(p.calls for p in providers.values()) == 0
    assert verdict.council_trace.completed == list(CouncilStage)

@pytest.mark.asyncio
async def test_only_relevant_specialists_are_called():
    sara,providers=build()
    verdict=await sara.solve(Problem(query="Analyze dashboard metrics"))
    assert providers["data_analytics"].calls == 1
    assert sum(p.calls for n,p in providers.items() if n!="data_analytics") == 0

@pytest.mark.asyncio
async def test_governance_block_prevents_provider_execution_but_not_internal_stage_trace():
    sara,providers=build(governance=FakeGovernance(Disposition.BLOCK))
    verdict=await sara.solve(Problem(query="Research latest market data"))
    assert sum(p.calls for p in providers.values()) == 0
    assert verdict.governance.disposition == Disposition.BLOCK
    assert verdict.council_trace.completed == list(CouncilStage)

@pytest.mark.asyncio
async def test_requested_action_is_advisory_and_never_executed_by_council():
    sara,_=build()
    verdict=await sara.solve(Problem(query="Deploy this", requested_action="deploy to production", authority_level=5))
    assert "execution" in verdict.next_action.lower() or verdict.next_action == "none"
    assert verdict.council_trace.completed == list(CouncilStage)

@pytest.mark.asyncio
async def test_non_durable_reasoning_is_explicit_when_signer_unavailable():
    sara,_=build(signed_ledger=FakeSignedLedger(fail=True))
    verdict=await sara.solve(Problem(query="Explain a triangle"))
    assert verdict.integrity.durable is False
    assert verdict.integrity.status.startswith("NON_DURABLE")
    assert verdict.decision_id is None

@pytest.mark.asyncio
async def test_durable_verdict_requires_successful_record_stage():
    sara,_=build()
    verdict=await sara.solve(Problem(query="Explain a triangle"))
    assert verdict.integrity.durable is True
    assert verdict.decision_id is not None
    assert verdict.council_trace.completed[-1] == CouncilStage.RECORD
