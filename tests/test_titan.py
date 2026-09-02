from app.module_awareness import ModuleAwarenessEngine, ModuleRecord
from app.titan import (
    BusSubscribeRequest,
    DeploymentGateRequest,
    ExecuteGateRequest,
    SovereigntySweepRequest,
    TitanEngine,
    VoiceEventRequest,
)


def titan():
    return TitanEngine(ModuleAwarenessEngine(), secret="test-titan-secret")


def test_titan_signs_and_verifies_voice_event():
    engine = titan()
    emitted = engine.emit(VoiceEventRequest(event_type="VALIDATE", chain_id="c1", sequence=0))

    verified = engine.verify_event(emitted["event"])

    assert verified["valid"] is True
    assert len(emitted["signature"]) == 128


def test_titan_rejects_tampered_voice_event():
    engine = titan()
    emitted = engine.emit(VoiceEventRequest(event_type="VALIDATE", chain_id="c1", sequence=0))
    event = dict(emitted["event"])
    event["data"] = {"tampered": True}

    verified = engine.verify_event(event)

    assert verified["valid"] is False


def test_titan_bus_rejects_out_of_order_event():
    engine = titan()
    emitted = engine.emit(VoiceEventRequest(event_type="ORCHESTRATE", chain_id="c1", sequence=1))

    result = engine.publish(emitted["event"])

    assert result["accepted"] is False
    assert result["reason"] == "sequence out of order"


def test_titan_deployment_gate_requires_written_approval():
    result = titan().deployment_gate(
        DeploymentGateRequest(service="sara-voice-ui", revision="sara-voice-ui-00001", architect_approval="DENIED")
    )

    assert result["approved"] is False


def test_titan_apex_execute_gate_requires_complete_valid_chain():
    engine = titan()
    chain_id = "chain-complete"
    previous = ""
    for sequence, event_type in enumerate(["VALIDATE", "ORCHESTRATE", "INTEGRATE", "CERTIFY", "EXECUTE"]):
        emitted = engine.emit(
            VoiceEventRequest(
                event_type=event_type,
                chain_id=chain_id,
                sequence=sequence,
                prev_signature=previous,
            )
        )
        previous = emitted["signature"]

    result = engine.execute_gate(
        ExecuteGateRequest(
            chain_id=chain_id,
            target_service="sara-voice-ui",
            action="promote",
            architect_approval="APPROVED",
        )
    )

    assert result["execute_authorized"] is True
    assert result["chain_event_count"] == 5


def test_titan_apex_blocks_incomplete_chain():
    engine = titan()
    engine.emit(VoiceEventRequest(event_type="VALIDATE", chain_id="short", sequence=0))

    result = engine.execute_gate(
        ExecuteGateRequest(
            chain_id="short",
            target_service="sara-voice-ui",
            action="promote",
            architect_approval="APPROVED",
        )
    )

    assert result["execute_authorized"] is False
    assert any("missing required VOICE event" in violation for violation in result["violations"])


def test_titan_sovereignty_sweep_reuses_module_awareness_audit():
    awareness = ModuleAwarenessEngine()
    awareness.register(
        ModuleRecord(
            service="sara-bad-module",
            url="http://unsafe.local",
            status="live",
        )
    )
    engine = TitanEngine(awareness, secret="test-titan-secret")

    result = engine.sovereignty_sweep(SovereigntySweepRequest())

    assert result["sovereign"] is False
    assert result["violation_count"] >= 1


def test_titan_subscribes_once_per_event_type():
    engine = titan()
    req = BusSubscribeRequest(event_type="EXECUTE", subscriber_url="https://subscriber.example/hook")

    engine.subscribe(req)
    engine.subscribe(req)

    assert engine.subscribers["EXECUTE"] == ["https://subscriber.example/hook"]
