from __future__ import annotations

from pathlib import Path

import pytest

from app.memory import ConversationMemory, EncryptedStateStore, MemoryKeyError
from app.module_awareness import MemoryConsolidation, ModuleAwarenessEngine, ModuleRecord, NarrativeEntry


def _set_memory_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "11" * 32)
    monkeypatch.delenv("SARA_MEMORY_KEY_B64", raising=False)
    monkeypatch.delenv("SARA_FAILSAFE_MASTER_KEY_HEX", raising=False)
    monkeypatch.delenv("SARA_FAILSAFE_MASTER_KEY_B64", raising=False)


def test_conversation_memory_recovers_after_restart_without_plaintext(monkeypatch, tmp_path):
    _set_memory_env(monkeypatch, tmp_path)
    phrase = "restart-only-private-phrase-49317"
    messages = [
        {"role": "user", "content": phrase},
        {"role": "assistant", "content": "Durable response."},
    ]

    first = ConversationMemory.from_env(required=True)
    first.save("session-restart-1", messages)

    second = ConversationMemory.from_env(required=True)
    assert second.load("session-restart-1") == messages

    raw = (tmp_path / "sara_omega.db").read_bytes()
    assert phrase.encode() not in raw
    assert b"session-restart-1" not in raw


def test_conversation_memory_fails_closed_without_an_encryption_key(monkeypatch, tmp_path):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    for key in (
        "SARA_MEMORY_KEY_HEX",
        "SARA_MEMORY_KEY_B64",
        "SARA_FAILSAFE_MASTER_KEY_HEX",
        "SARA_FAILSAFE_MASTER_KEY_B64",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(MemoryKeyError):
        ConversationMemory.from_env(required=True)

    assert ConversationMemory.from_env(required=False) is None


def test_module_awareness_continuity_survives_restart_encrypted(monkeypatch, tmp_path):
    _set_memory_env(monkeypatch, tmp_path)
    phrase = "module-continuity-private-phrase-76190"
    store = EncryptedStateStore.from_env(required=True)
    first = ModuleAwarenessEngine(state_store=store)
    first.register(ModuleRecord(service="sara-custom-durable", url="https://example.invalid", status="live"))
    first.append_narrative(
        NarrativeEntry(session_id="continuity-session", actor="user", content=phrase)
    )
    first.consolidate(
        MemoryConsolidation(
            session_id="continuity-session",
            summary="Durable continuity",
            key_facts=["state survives restart"],
            strategic_intents=["preserve module awareness"],
        )
    )

    second = ModuleAwarenessEngine(state_store=EncryptedStateStore.from_env(required=True))

    assert "sara-custom-durable" in second.registry
    assert second.continuity("continuity-session")["continuity_intact"] is True
    assert second.get_narrative("continuity-session")["entries"][0]["content"] == phrase

    raw = (tmp_path / "sara_omega.db").read_bytes()
    assert phrase.encode() not in raw


def test_runtime_think_is_wired_to_encrypted_conversation_store():
    source = Path("main.py").read_text(encoding="utf-8")
    assert "ConversationMemory" in source
    assert "CONVERSATION_MEMORY.load(session_id)" in source
    assert "CONVERSATION_MEMORY.save(session_id, ctx)" in source
