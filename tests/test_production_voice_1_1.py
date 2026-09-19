from fastapi.testclient import TestClient

import main


class FakeVoiceClient:
    def __init__(self):
        self.calls = []

    def synthesize_with_controls(self, text, controls):
        self.calls.append((text, controls.length_scale))
        return b"RIFFvoice-1-1"


client = TestClient(main.app)


def _owner(monkeypatch):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "OWNER_TOKEN", "owner-token")
    return {"Authorization": "Bearer owner-token"}


def _action(monkeypatch):
    monkeypatch.setattr(main, "KILL_SWITCH", False)
    monkeypatch.setattr(main, "GPT_ACTION_TOKEN", "action-token")
    return {"Authorization": "Bearer action-token"}


def test_voice_1_1_routes_fail_closed_when_disabled(monkeypatch):
    monkeypatch.delenv("SARA_VOICE_1_1_ENABLED", raising=False)

    response = client.post(
        "/v1/voice/jobs",
        headers=_owner(monkeypatch),
        json={"text": "Hello."},
    )

    assert response.status_code == 503


def test_voice_1_1_job_is_owner_only_and_returns_receipts(monkeypatch):
    fake = FakeVoiceClient()
    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_1_1_ENABLED", "true")
    monkeypatch.setenv("SARA_PIPER_SERVICE_URL", "http://voice.internal:8080")
    monkeypatch.setenv("SARA_PIPER_SERVICE_TOKEN", "unit-token")
    monkeypatch.setattr(main, "_piper_voice_client", fake, raising=False)
    monkeypatch.setattr(main, "_voice_1_1_job_manager", None, raising=False)

    denied = client.post(
        "/v1/voice/jobs",
        headers=_action(monkeypatch),
        json={"text": "SARA is online."},
    )
    assert denied.status_code == 403

    created = client.post(
        "/v1/voice/jobs",
        headers=_owner(monkeypatch),
        json={
            "text": "SARA is online. Voice 1.1 is ready.",
            "speech_rate": "normal",
            "preserve_transcript": False,
            "return_audio": "segments",
        },
    )

    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "completed"
    assert body["source_response_sha256"]
    assert len(body["segments"]) == 2
    assert "SARA is online" not in str(body)

    job_id = body["job_id"]
    receipts = client.get(f"/v1/voice/jobs/{job_id}/receipts", headers=_owner(monkeypatch))
    assert receipts.status_code == 200
    assert len(receipts.json()["receipts"]) == 2
    assert "unit-token" not in receipts.text


def test_voice_1_1_stop_is_owner_only_and_idempotent(monkeypatch):
    fake = FakeVoiceClient()
    monkeypatch.setenv("SARA_VOICE_ENABLED", "true")
    monkeypatch.setenv("SARA_VOICE_1_1_ENABLED", "true")
    monkeypatch.setenv("SARA_PIPER_SERVICE_URL", "http://voice.internal:8080")
    monkeypatch.setenv("SARA_PIPER_SERVICE_TOKEN", "unit-token")
    monkeypatch.setattr(main, "_piper_voice_client", fake, raising=False)
    monkeypatch.setattr(main, "_voice_1_1_job_manager", None, raising=False)

    created = client.post("/v1/voice/jobs", headers=_owner(monkeypatch), json={"text": "One. Two."})
    job_id = created.json()["job_id"]

    denied = client.post(f"/v1/voice/jobs/{job_id}/stop", headers=_action(monkeypatch))
    first = client.post(f"/v1/voice/jobs/{job_id}/stop", headers=_owner(monkeypatch))
    second = client.post(f"/v1/voice/jobs/{job_id}/stop", headers=_owner(monkeypatch))

    assert denied.status_code == 403
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] in {"completed", "stopped"}
    assert second.json()["stop_requested_at"] is not None


def test_public_accessibility_voice_routes_are_not_exposed_in_1_1(monkeypatch):
    monkeypatch.setenv("SARA_VOICE_1_1_ENABLED", "true")
    monkeypatch.delenv("SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED", raising=False)

    response = client.post("/v1/accessibility/voice/jobs", json={"text": "Hello."})

    assert response.status_code in {403, 404}
