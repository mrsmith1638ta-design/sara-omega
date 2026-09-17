import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

import main


class FakePiperVoiceClient:
    def __init__(self, audio: bytes = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 64):
        self.audio = audio
        self.texts: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.texts.append(text)
        return self.audio


def _configure_voice_action(monkeypatch, tmp_path: Path, fake: FakePiperVoiceClient):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "GPT_ACTION_TOKEN", "gpt-action-token")
    monkeypatch.setattr(main, "OWNER_TOKEN", "owner-token")
    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_MAX_CHARACTERS", "4000")
    monkeypatch.setenv("SARA_GPT_VOICE_ARTIFACT_DIR", str(tmp_path / "voice-artifacts"))
    monkeypatch.setenv("SARA_GPT_VOICE_ARTIFACT_TTL_SECONDS", "600")
    monkeypatch.setenv("SARA_PUBLIC_BASE_URL", "https://sara.example")
    monkeypatch.setattr(main, "_piper_voice_client", fake, raising=False)
    main.AUDIT.clear()


def test_gpt_action_voice_returns_playable_artifact_and_receipt(monkeypatch, tmp_path):
    fake = FakePiperVoiceClient()
    _configure_voice_action(monkeypatch, tmp_path, fake)
    client = TestClient(main.app, base_url="https://sara.example")

    text = "SARA, speak from inside this GPT chat."
    response = client.post(
        "/gpt/action/voice/speak",
        headers={"Authorization": "Bearer gpt-action-token"},
        json={"text": text},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "sara-chatgpt-action-voice"
    assert body["artifact"]["content_type"] == "audio/wav"
    assert body["artifact"]["url"].startswith("https://sara.example/gpt/action/voice/artifacts/")
    assert body["artifact"]["sha256"] == hashlib.sha256(fake.audio).hexdigest()
    assert body["receipt"]["text_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert body["receipt"]["profile_id"] == "sara_elegant_british_v1"
    assert body["receipt"]["source_commit_sha"]
    assert body["secrets_included"] is False
    assert text not in str(body)
    assert fake.texts == [text]

    artifact = client.get(body["artifact"]["url"].replace("https://sara.example", ""))
    assert artifact.status_code == 200
    assert artifact.headers["content-type"] == "audio/wav"
    assert artifact.headers["cache-control"] == "private, no-store"
    assert artifact.content == fake.audio


def test_gpt_action_voice_requires_action_token_not_owner(monkeypatch, tmp_path):
    fake = FakePiperVoiceClient()
    _configure_voice_action(monkeypatch, tmp_path, fake)
    client = TestClient(main.app, base_url="https://sara.example")

    owner = client.post(
        "/gpt/action/voice/speak",
        headers={"Authorization": "Bearer owner-token"},
        json={"text": "Owner token must not drive the GPT action voice path."},
    )
    missing = client.post("/gpt/action/voice/speak", json={"text": "No token."})

    assert owner.status_code == 403
    assert missing.status_code == 401
    assert fake.texts == []


def test_gpt_action_voice_schema_exposes_chat_speak_operation():
    schema = Path("chatgpt-gpt-action.yaml").read_text(encoding="utf-8")

    assert "/gpt/action/voice/speak:" in schema
    assert "operationId: saraOmegaSpeakInChat" in schema
    assert "audio_url" in schema
    assert "GPTActionVoiceSpeakRequest" in schema
