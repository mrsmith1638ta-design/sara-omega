from app.module_awareness import (
    HarmonizeRequest,
    MemoryConsolidation,
    ModuleAwarenessEngine,
    ModuleRecord,
    NarrativeEntry,
    ONTOLOGICAL_ANCHOR,
)


def test_module_awareness_counts_sovereign_modules_without_infrastructure():
    awareness = ModuleAwarenessEngine(baseline_count=215)
    awareness.register(ModuleRecord(service="sara-business-module", url="https://sara-business-module-i7iay5r2wq-uc.a.run.app", status="live"))

    count = awareness.count()

    assert count["sovereign_module_count"] == 1
    assert count["baseline"] == 215
    assert count["delta"] == -214


def test_query_harmonization_resolves_legacy_voice_alias_without_forwarding():
    awareness = ModuleAwarenessEngine()
    awareness.register(ModuleRecord(service="sara-voice-api", url="https://sara-voice-api-i7iay5r2wq-uc.a.run.app", status="live"))

    result = awareness.harmonize(HarmonizeRequest(target_service="sara-voice-api", path="/api/voice"))

    assert result["resolved_path"] == "/v1/voice/text"
    assert result["forwarded"] is False


def test_governance_audit_detects_anchor_and_stale_url_violations():
    awareness = ModuleAwarenessEngine()
    awareness.register(
        ModuleRecord(
            service="sara-bad-module",
            url="https://sara-bad-module-667977407542.us-central1.run.app",
            status="live",
            ontological_anchor="wrong",
        )
    )

    audit = awareness.audit("sara-bad-module")
    violations = audit["violations"][0]["violations"]

    assert "ontological_anchor_mismatch" in violations
    assert "stale_url_hash" in violations


def test_continuity_requires_narrative_and_consolidation():
    awareness = ModuleAwarenessEngine()
    session_id = "session-1"

    assert awareness.continuity(session_id)["continuity_intact"] is False

    awareness.append_narrative(NarrativeEntry(session_id=session_id, actor="user", content="Keep runtime assurance active."))
    awareness.consolidate(
        MemoryConsolidation(
            session_id=session_id,
            summary="Runtime assurance integration",
            key_facts=["Module awareness is integrated."],
        )
    )

    assert awareness.continuity(session_id)["continuity_intact"] is True


def test_temporal_context_contains_anchor_and_epoch():
    temporal = ModuleAwarenessEngine().temporal_context()

    assert temporal["anchor"] == ONTOLOGICAL_ANCHOR
    assert temporal["epoch_seconds"] > 0
