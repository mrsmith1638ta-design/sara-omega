import hashlib
import json
from dataclasses import replace

from fastapi.testclient import TestClient


class FakeVoiceClient:
    def __init__(self, audio=b"RIFFfake-wav"):
        self.audio = audio
        self.calls = []

    def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        return self.audio


def test_sara_voice_profile_is_fixed_british_cori():
    from sara_unified.voice.profile import SARA_VOICE_PROFILE

    assert SARA_VOICE_PROFILE.profile_id == "sara_elegant_british_v1"
    assert SARA_VOICE_PROFILE.model_id == "en_GB-cori-high"
    assert SARA_VOICE_PROFILE.language == "en-GB"
    assert SARA_VOICE_PROFILE.length_scale == 1.08
    assert SARA_VOICE_PROFILE.noise_scale == 0.55
    assert SARA_VOICE_PROFILE.noise_w_scale == 0.70
    assert SARA_VOICE_PROFILE.volume == 0.95


def test_piper_client_rejects_empty_audio(monkeypatch):
    from sara_unified.voice.client import PiperVoiceClient, VoiceSynthesisError

    class Response:
        status_code = 200
        content = b""
        headers = {"content-type": "audio/wav"}

    class Client:
        def post(self, *args, **kwargs):
            return Response()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr("sara_unified.voice.client.httpx.Client", lambda **kwargs: Client())
    client = PiperVoiceClient("http://piper", "secret", timeout_seconds=2)

    try:
        client.synthesize("hello")
        assert False, "expected VoiceSynthesisError"
    except VoiceSynthesisError:
        pass


def test_piper_client_sends_fixed_profile_settings(monkeypatch):
    from sara_unified.voice.client import PiperVoiceClient

    captured = {}

    class Response:
        status_code = 200
        content = b"RIFFok"
        headers = {"content-type": "audio/wav"}

    class Client:
        def post(self, url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return Response()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr("sara_unified.voice.client.httpx.Client", lambda **kwargs: Client())
    audio = PiperVoiceClient("http://piper/", "secret", timeout_seconds=2).synthesize("hello")

    assert audio == b"RIFFok"
    assert captured["url"] == "http://piper/synthesize"
    assert captured["headers"]["X-SARA-VOICE-TOKEN"] == "secret"
    assert captured["json"] == {
        "text": "hello",
        "length_scale": 1.08,
        "noise_scale": 0.55,
        "noise_w_scale": 0.70,
        "volume": 0.95,
    }


def test_settings_parse_voice_environment(monkeypatch):
    from sara_unified.config import Settings

    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_PIPER_SERVICE_URL", "http://voice.internal:5000")
    monkeypatch.setenv("SARA_PIPER_SERVICE_TOKEN", "token-1")
    monkeypatch.setenv("SARA_VOICE_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("SARA_VOICE_MAX_CHARACTERS", "1200")

    settings = Settings.from_env()
    assert settings.voice_enabled is True
    assert settings.piper_service_url == "http://voice.internal:5000"
    assert settings.piper_service_token == "token-1"
    assert settings.voice_timeout_seconds == 7.5
    assert settings.voice_max_characters == 1200


def test_voice_api_is_unauthorized_without_role(tmp_path):
    from sara_unified.app import SARAUnified
    from sara_unified.config import Settings
    from sara_unified.evidence.audit import AuditLedger

    settings = replace(Settings(), voice_enabled=True)
    app = SARAUnified(AuditLedger(tmp_path / "audit.jsonl"), settings=settings, voice_client=FakeVoiceClient())
    client = TestClient(app.api)

    response = client.post("/v1/voice/synthesize", json={"text": "hello"})
    assert response.status_code == 401


def test_voice_api_disabled_fails_closed(tmp_path):
    from sara_unified.app import SARAUnified
    from sara_unified.config import Settings
    from sara_unified.evidence.audit import AuditLedger

    app = SARAUnified(
        AuditLedger(tmp_path / "audit.jsonl"),
        settings=Settings(),
        voice_client=FakeVoiceClient(),
        allow_local_operator=True,
    )
    client = TestClient(app.api)

    response = client.post(
        "/v1/voice/synthesize",
        headers={"Authorization": "Bearer local-operator"},
        json={"text": "hello"},
    )
    assert response.status_code == 503


def test_voice_api_rejects_empty_and_oversized_text(tmp_path):
    from sara_unified.app import SARAUnified
    from sara_unified.config import Settings
    from sara_unified.evidence.audit import AuditLedger

    settings = replace(Settings(), voice_enabled=True, voice_max_characters=5)
    app = SARAUnified(
        AuditLedger(tmp_path / "audit.jsonl"),
        settings=settings,
        voice_client=FakeVoiceClient(),
        allow_local_operator=True,
    )
    client = TestClient(app.api)
    headers = {"Authorization": "Bearer local-operator"}

    assert client.post("/v1/voice/synthesize", headers=headers, json={"text": "   "}).status_code == 422
    assert client.post("/v1/voice/synthesize", headers=headers, json={"text": "123456"}).status_code == 422


def test_voice_api_returns_wav_and_audits_digest_not_raw_text(tmp_path):
    from sara_unified.app import SARAUnified
    from sara_unified.config import Settings
    from sara_unified.evidence.audit import AuditLedger

    phrase = "SARA voice online"
    audit_path = tmp_path / "audit.jsonl"
    fake = FakeVoiceClient(b"RIFFvoice-bytes")
    settings = replace(Settings(), voice_enabled=True)
    app = SARAUnified(
        AuditLedger(audit_path),
        settings=settings,
        voice_client=fake,
        allow_local_operator=True,
    )
    client = TestClient(app.api)

    response = client.post(
        "/v1/voice/synthesize",
        headers={"Authorization": "Bearer local-operator"},
        json={"text": phrase},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content == b"RIFFvoice-bytes"
    assert fake.calls == [phrase]

    records = [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]
    event = records[-1]
    assert event["action"] == "VOICE_SYNTHESIZED"
    assert event["details"]["profile_id"] == "sara_elegant_british_v1"
    assert event["details"]["character_count"] == len(phrase)
    assert event["details"]["text_sha256"] == hashlib.sha256(phrase.encode("utf-8")).hexdigest()
    assert phrase not in audit_path.read_text()


def test_voice_profile_and_capability_are_exposed(tmp_path):
    from sara_unified.app import SARAUnified

    app = SARAUnified.local(audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app.api)

    profile = client.get("/v1/voice/profile")
    assert profile.status_code == 200
    assert profile.json()["profile_id"] == "sara_elegant_british_v1"
    assert profile.json()["model_id"] == "en_GB-cori-high"

    capabilities = client.get("/v1/capabilities").json()["capabilities"]
    assert "voice-synthesis" in capabilities
