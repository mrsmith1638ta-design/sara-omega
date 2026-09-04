from __future__ import annotations

from pathlib import Path

import pytest

from app.memory import ConversationMemory


def _memory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ConversationMemory:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "61" * 32)
    value = ConversationMemory.from_env(required=True)
    assert value is not None
    return value


def test_same_user_has_continuity_across_different_chat_sessions(monkeypatch, tmp_path):
    memory = _memory(monkeypatch, tmp_path)
    user_uuid = "11111111-1111-4111-8111-111111111111"
    first = [
        {"role": "user", "content": "My project is Atlas."},
        {"role": "assistant", "content": "I will retain that in SARA continuity."},
    ]
    memory.save_for_user(user_uuid, "chat-one", first)
    continuity = memory.update_user_continuity(user_uuid, session_id="chat-one", messages=first)

    assert continuity["thread_count"] == 1
    assert memory.load_for_user(user_uuid, "chat-one") == first
    assert memory.load_for_user(user_uuid, "chat-two") == []
    recovered = memory.load_user_continuity(user_uuid)
    assert "My project is Atlas." in str(recovered)

    second = [{"role": "user", "content": "What project was I working on?"}]
    memory.save_for_user(user_uuid, "chat-two", second)
    memory.update_user_continuity(user_uuid, session_id="chat-two", messages=second)
    assert memory.load_user_continuity(user_uuid)["thread_count"] == 2


def test_two_users_with_same_session_id_are_isolated(monkeypatch, tmp_path):
    memory = _memory(monkeypatch, tmp_path)
    user_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    user_b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    session = "shared-looking-chat-id"
    memory.save_for_user(user_a, session, [{"role": "user", "content": "A-only-secret"}])
    memory.save_for_user(user_b, session, [{"role": "user", "content": "B-only-secret"}])

    assert memory.load_for_user(user_a, session)[0]["content"] == "A-only-secret"
    assert memory.load_for_user(user_b, session)[0]["content"] == "B-only-secret"


def test_user_continuity_survives_restart_without_plaintext_identifiers(monkeypatch, tmp_path):
    first = _memory(monkeypatch, tmp_path)
    user_uuid = "22222222-2222-4222-8222-222222222222"
    session_id = "private-cross-chat-session"
    phrase = "cross-chat-private-memory-77441"
    messages = [{"role": "user", "content": phrase}]
    first.save_for_user(user_uuid, session_id, messages)
    first.update_user_continuity(user_uuid, session_id=session_id, messages=messages)

    second = ConversationMemory.from_env(required=True)
    assert second is not None
    assert second.load_for_user(user_uuid, session_id) == messages
    assert phrase in str(second.load_user_continuity(user_uuid))

    raw = (tmp_path / "sara_omega.db").read_bytes()
    assert user_uuid.encode() not in raw
    assert session_id.encode() not in raw
    assert phrase.encode() not in raw


def test_forget_user_removes_only_that_users_encrypted_memory(monkeypatch, tmp_path):
    memory = _memory(monkeypatch, tmp_path)
    user_a = "33333333-3333-4333-8333-333333333333"
    user_b = "44444444-4444-4444-8444-444444444444"
    memory.save_for_user(user_a, "a1", [{"role": "user", "content": "remove-me"}])
    memory.update_user_continuity(user_a, session_id="a1", messages=memory.load_for_user(user_a, "a1"))
    memory.save_for_user(user_b, "b1", [{"role": "user", "content": "keep-me"}])
    memory.update_user_continuity(user_b, session_id="b1", messages=memory.load_for_user(user_b, "b1"))

    memory.forget_user(user_a)

    assert memory.load_for_user(user_a, "a1") == []
    assert memory.load_user_continuity(user_a)["thread_count"] == 0
    assert memory.load_for_user(user_b, "b1")[0]["content"] == "keep-me"
    assert memory.load_user_continuity(user_b)["thread_count"] == 1


def test_user_thread_index_is_bounded(monkeypatch, tmp_path):
    monkeypatch.setenv("SARA_MEMORY_CONTINUITY_MAX_ITEMS", "3")
    memory = _memory(monkeypatch, tmp_path)
    user_uuid = "55555555-5555-4555-8555-555555555555"
    for index in range(5):
        session = f"chat-{index}"
        messages = [{"role": "user", "content": f"message-{index}"}]
        memory.save_for_user(user_uuid, session, messages)
        memory.update_user_continuity(user_uuid, session_id=session, messages=messages)

    continuity = memory.load_user_continuity(user_uuid)
    assert continuity["thread_count"] == 3
    assert len(memory.list_user_threads(user_uuid, limit=20)) == 3
    assert "chat-0" not in str(continuity)
