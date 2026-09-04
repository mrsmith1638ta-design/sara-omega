from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.user_identity import UserIdentityStore
from app.user_gateway import router
import app.user_gateway as user_gateway


CLIENT_ID = "sara-custom-gpt-test"
CLIENT_SECRET = "x" * 48
CALLBACK = "https://chat.openai.com/aip/g-test/oauth/callback"
ACTION_TOKEN = "a" * 48
TEST_TOKEN = "t" * 48
PASSWORD_A = "Unit-Test-Password-7!Alpha"
PASSWORD_B = "Unit-Test-Password-8!Bravo"


class _FakeFailSafe:
    required = True

    def __init__(self):
        self.checkpoints = []

    def ensure_ready(self):
        return None

    def checkpoint(self, state, event, *, correlation_id="", metadata=None):
        self.checkpoints.append((state, event, dict(metadata or {})))
        return SimpleNamespace(snapshot_id="test-snapshot")


class _FakeSara:
    def __init__(self):
        self.problems = []

    async def solve(self, problem):
        self.problems.append(problem)
        return SimpleNamespace(
            decision="Remembered answer",
            why="Governed user-memory test verdict",
            confidence=0.9,
            decision_id="decision-test-1",
            model_dump=lambda: {
                "decision": "Remembered answer",
                "why": "Governed user-memory test verdict",
                "confidence": 0.9,
                "decision_id": "decision-test-1",
            },
        )


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_MEMORY_KEY_HEX", "71" * 32)
    monkeypatch.setenv("SARA_ENROLLMENT_ID", "SARA-NEW-USER")
    monkeypatch.setenv("SARA_OAUTH_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("SARA_OAUTH_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("SARA_OAUTH_REDIRECT_URIS", CALLBACK)
    monkeypatch.setenv("SARA_OAUTH_SCOPE", "sara.memory sara.solve")
    monkeypatch.setenv("GPT_ACTION_TOKEN", ACTION_TOKEN)
    monkeypatch.setenv("TEST_TOKEN", TEST_TOKEN)


def _create_token(password: str = PASSWORD_A):
    store = UserIdentityStore.from_env(required=True)
    assert store is not None
    invite = store.create_invitation(base_url="https://sara.example", ttl_seconds=3600)
    account = store.enroll(
        invite_token=invite.token,
        enrollment_id="SARA-NEW-USER",
        password=password,
        password_confirm=password,
    )
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id=CLIENT_ID,
        redirect_uri=CALLBACK,
        scope="sara.memory sara.solve",
    )
    bundle = store.exchange_authorization_code(
        code=code,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
    )
    return account, bundle.access_token


def _client(monkeypatch):
    fake_sara = _FakeSara()
    fake_failsafe = _FakeFailSafe()
    monkeypatch.setattr(user_gateway, "GATEWAY_SARA", fake_sara)
    monkeypatch.setattr(user_gateway, "FAILSAFE", fake_failsafe)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), fake_sara, fake_failsafe


def test_personal_gateway_rejects_shared_action_and_test_tokens(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    client, _sara, _failsafe = _client(monkeypatch)
    for token in (ACTION_TOKEN, TEST_TOKEN):
        response = client.post(
            "/gpt/user/gateway",
            headers={"Authorization": f"Bearer {token}"},
            json={"operation": "memory_status"},
        )
        assert response.status_code == 401


def test_same_oauth_user_carries_continuity_across_new_chat_ids(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    account, token = _create_token()
    client, sara, failsafe = _client(monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "solve", "query": "My project is Atlas.", "session_id": "chat-one"},
    )
    assert first.status_code == 200
    assert first.json()["public_user_id"] == account.public_user_id
    assert first.json()["session_id"] == "chat-one"
    assert sara.problems[-1].actor == "sara_oauth_user"
    assert sara.problems[-1].authority_level == 1

    second = client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "solve", "query": "What was I working on?", "session_id": "chat-two"},
    )
    assert second.status_code == 200
    continuity = sara.problems[-1].context["sara_user_continuity"]
    assert "My project is Atlas." in str(continuity)
    assert len(failsafe.checkpoints) >= 2


def test_two_oauth_users_are_memory_isolated_even_with_same_session_id(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    account_a, token_a = _create_token(PASSWORD_A)
    account_b, token_b = _create_token(PASSWORD_B)
    assert account_a.user_uuid != account_b.user_uuid
    client, sara, _failsafe = _client(monkeypatch)

    response_a = client.post(
        "/gpt/user/gateway",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"operation": "solve", "query": "A-private-project", "session_id": "same-chat-id"},
    )
    assert response_a.status_code == 200
    response_b = client.post(
        "/gpt/user/gateway",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"operation": "solve", "query": "B-private-project", "session_id": "same-chat-id"},
    )
    assert response_b.status_code == 200
    assert "A-private-project" not in str(sara.problems[-1].context["sara_user_continuity"])


def test_memory_status_recall_and_confirmed_forget(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    account, token = _create_token()
    client, _sara, _failsafe = _client(monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "solve", "query": "Remember this continuity phrase.", "session_id": "thread-1"},
    )
    status = client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "memory_status"},
    )
    assert status.status_code == 200
    assert status.json()["public_user_id"] == account.public_user_id
    assert status.json()["thread_count"] == 1

    recall = client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "memory_recall"},
    )
    assert recall.status_code == 200
    assert "Remember this continuity phrase." in str(recall.json()["continuity"])

    denied = client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "memory_forget", "context": {"confirm": False}},
    )
    assert denied.status_code == 400
    deleted = client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "memory_forget", "context": {"confirm": True}},
    )
    assert deleted.status_code == 200
    assert deleted.json()["forgotten"] is True
    empty = client.post(
        "/gpt/user/gateway",
        headers=headers,
        json={"operation": "memory_status"},
    )
    assert empty.json()["thread_count"] == 0


def test_user_gateway_generates_thread_id_when_chat_id_is_absent(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    _account, token = _create_token()
    client, _sara, _failsafe = _client(monkeypatch)
    response = client.post(
        "/gpt/user/gateway",
        headers={"Authorization": f"Bearer {token}"},
        json={"operation": "solve", "query": "Start a new isolated thread."},
    )
    assert response.status_code == 200
    assert response.json()["session_id"]
    assert len(response.json()["session_id"]) <= 64
