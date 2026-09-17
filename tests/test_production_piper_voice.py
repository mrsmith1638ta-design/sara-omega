from fastapi.testclient import TestClient

import main


class FakePiperVoiceClient:
    def __init__(self, audio: bytes = b"RIFFproduction-voice"):
        self.audio = audio
        self.texts: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.texts.append(text)
        return self.audio


client = TestClient(main.app)


def _owner_auth(monkeypatch):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "OWNER_TOKEN", "owner-voice-token")
    return {"Authorization": "Bearer owner-voice-token"}


def test_production_entrypoint_exposes_governed_voice_profile():
    response = client.get("/v1/voice/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["profile_id"] == "sara_elegant_british_v1"
    assert body["model_id"] == "en_GB-cori-high"
    assert body["language"] == "en-GB"


def test_production_entrypoint_synthesizes_wav_and_audits_digest_only(monkeypatch):
    phrase = "SARA OMEGA Piper voice is live."
    fake = FakePiperVoiceClient()
    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_MAX_CHARACTERS", "4000")
    monkeypatch.setattr(main, "_piper_voice_client", fake, raising=False)
    main.AUDIT.clear()

    response = client.post(
        "/v1/voice/synthesize",
        headers=_owner_auth(monkeypatch),
        json={"text": phrase},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFFproduction-voice"
    assert fake.texts == [phrase]
    assert main.AUDIT[-1]["event"] == "piper_voice_synthesized"
    assert main.AUDIT[-1]["details"]["profile_id"] == "sara_elegant_british_v1"
    assert main.AUDIT[-1]["details"]["character_count"] == len(phrase)
    assert "text_sha256" in main.AUDIT[-1]["details"]
    assert phrase not in str(main.AUDIT[-1])
