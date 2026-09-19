from fastapi import FastAPI
from fastapi.testclient import TestClient

import main
import sara_web


class FakePiperVoiceClient:
    def __init__(self, audio: bytes = b"RIFFvoice-console"):
        self.audio = audio
        self.texts: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.texts.append(text)
        return self.audio


def _client() -> TestClient:
    app = FastAPI()
    sara_web.register_ui_routes(app)
    return TestClient(app, base_url="https://testserver")


def _configure_owner(monkeypatch, token: str = "owner-console-token") -> str:
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "OWNER_TOKEN", token)
    return token


def _login(client: TestClient, token: str):
    return client.post("/voice-console/session", json={"owner_token": token})


def test_voice_console_page_is_fixed_profile_and_never_embeds_owner_secret(monkeypatch):
    token = _configure_owner(monkeypatch)
    client = _client()

    response = client.get("/voice-console")

    assert response.status_code == 200
    assert "SARA OMEGA Voice Console" in response.text
    assert "sara_elegant_british_v1" in response.text
    assert "en_GB-cori-high" in response.text
    assert "Speak" in response.text
    assert "Stop" in response.text
    assert token not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_voice_console_login_fails_closed_for_wrong_owner_token(monkeypatch):
    _configure_owner(monkeypatch)
    client = _client()

    response = _login(client, "wrong-token")

    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert "wrong-token" not in response.text


def test_voice_console_login_issues_short_lived_secure_httponly_cookie(monkeypatch):
    token = _configure_owner(monkeypatch)
    client = _client()

    response = _login(client, token)

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Max-Age=900" in cookie
    assert token not in cookie
    assert token not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_voice_console_synthesis_rejects_unauthenticated_browser(monkeypatch):
    _configure_owner(monkeypatch)
    client = _client()

    response = client.post("/voice-console/api/synthesize", json={"text": "Hello from SARA."})

    assert response.status_code == 401


def test_voice_console_synthesizes_through_governed_owner_piper_path(monkeypatch):
    token = _configure_owner(monkeypatch)
    fake = FakePiperVoiceClient()
    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_MAX_CHARACTERS", "4000")
    monkeypatch.setattr(main, "_piper_voice_client", fake, raising=False)
    main.AUDIT.clear()
    client = _client()
    assert _login(client, token).status_code == 200

    phrase = "Hello Tommy. This is SARA OMEGA."
    response = client.post("/voice-console/api/synthesize", json={"text": phrase})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFFvoice-console"
    assert fake.texts == [phrase]
    assert main.AUDIT[-1]["event"] == "piper_voice_synthesized"
    assert main.AUDIT[-1]["details"]["profile_id"] == "sara_elegant_british_v1"
    assert phrase not in str(main.AUDIT[-1])


def test_voice_console_keeps_server_side_text_bounds(monkeypatch):
    token = _configure_owner(monkeypatch)
    fake = FakePiperVoiceClient()
    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_MAX_CHARACTERS", "12")
    monkeypatch.setattr(main, "_piper_voice_client", fake, raising=False)
    client = _client()
    assert _login(client, token).status_code == 200

    blank = client.post("/voice-console/api/synthesize", json={"text": "   "})
    oversized = client.post("/voice-console/api/synthesize", json={"text": "x" * 13})

    assert blank.status_code == 422
    assert oversized.status_code == 422
    assert fake.texts == []


def test_voice_console_logout_invalidates_browser_session(monkeypatch):
    token = _configure_owner(monkeypatch)
    client = _client()
    assert _login(client, token).status_code == 200

    logout = client.delete("/voice-console/session")
    after = client.post("/voice-console/api/synthesize", json={"text": "Should not speak."})

    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False}
    assert after.status_code == 401


def test_voice_console_session_fails_closed_when_owner_token_rotates(monkeypatch):
    token = _configure_owner(monkeypatch)
    client = _client()
    assert _login(client, token).status_code == 200

    monkeypatch.setattr(main, "OWNER_TOKEN", "rotated-owner-token")
    response = client.post("/voice-console/api/synthesize", json={"text": "Old session must fail."})

    assert response.status_code == 401


def test_voice_console_rejects_foreign_origin_with_valid_owner_session(monkeypatch):
    token = _configure_owner(monkeypatch)
    fake = FakePiperVoiceClient()
    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_MAX_CHARACTERS", "4000")
    monkeypatch.setattr(main, "_piper_voice_client", fake, raising=False)
    client = _client()
    assert _login(client, token).status_code == 200

    response = client.post(
        "/voice-console/api/synthesize",
        json={"text": "Foreign origins must not drive owner voice."},
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert fake.texts == []
