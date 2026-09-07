from app.models import (
    CouncilStage,
    CouncilStageEvent,
    CouncilTrace,
    Disposition,
    GovernanceDecision,
    IntegrityStatus,
    SignatureRecord,
    Verdict,
)

EXPECTED = [
    CouncilStage.OBSERVE,
    CouncilStage.MAP,
    CouncilStage.EVALUATE,
    CouncilStage.GENERATE,
    CouncilStage.CROSS_EXAMINE,
    CouncilStage.STRESS_TEST,
    CouncilStage.SYNTHESIZE,
    CouncilStage.GOVERN,
    CouncilStage.VERDICT,
    CouncilStage.RECORD,
]


def test_council_trace_requires_canonical_stage_order():
    trace = CouncilTrace(stage_order=EXPECTED, completed=EXPECTED)
    assert trace.stage_order == EXPECTED
    assert trace.completed == EXPECTED
    assert trace.mandatory is True


def test_council_trace_rejects_noncanonical_stage_order():
    reversed_order = list(reversed(EXPECTED))
    try:
        CouncilTrace(stage_order=reversed_order, completed=[])
    except ValueError:
        pass
    else:
        raise AssertionError("noncanonical stage order must be rejected")


def test_integrity_defaults_are_explicitly_non_durable():
    status = IntegrityStatus()
    assert status.durable is False
    assert status.chain_valid is False
    assert status.read_after_write_verified is False


def test_signature_record_contains_only_public_signature_metadata():
    record = SignatureRecord(
        algorithm="Ed25519",
        key_id="kms-key-1",
        signature_b64="c2ln",
        verified=True,
        signer="external",
    )
    assert "private" not in " ".join(record.model_dump().keys()).lower()


def test_stage_event_bounds_metadata_and_defaults():
    event = CouncilStageEvent(stage=CouncilStage.OBSERVE, status="completed")
    assert event.detail == ""
    assert event.metadata == {}


def test_existing_callers_can_construct_verdict_without_new_fields():
    verdict = Verdict(
        decision="ANSWER",
        why="Backward compatible",
        confidence=0.8,
        next_action="return_result",
        governance=GovernanceDecision(disposition=Disposition.ALLOW),
    )
    assert verdict.request_id is None
    assert verdict.council_trace is None
    assert verdict.integrity.durable is False
    assert verdict.supersedes_decision_id is None
