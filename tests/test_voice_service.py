import hashlib

import pytest
from fastapi.testclient import TestClient


class FakePiperEngine:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, *, length_scale, noise_scale, noise_w_scale, volume):
        self.calls.append(
            {
                "text": text,
                "length_scale": length_scale,
                "noise_scale": noise_scale,
                "noise_w_scale": noise_w_scale,
                "volume": volume,
            }
        )
        return b"RIFFpiper-wav"


def test_voice_service_requires_service_token():
    from voice_service.app import create_voice_service

    with pytest.raises(RuntimeError, match="service token"):
        create_voice_service(engine=FakePiperEngine(), service_token="")


def test_voice_service_rejects_wrong_token():
    from voice_service.app import create_voice_service

    app = create_voice_service(engine=FakePiperEngine(), service_token="secret")
    client = TestClient(app)

    response = client.post("/synthesize", headers={"X-SARA-VOICE-TOKEN": "wrong"}, json={"text": "hello"})
    assert response.status_code == 401


def test_voice_service_returns_wav_with_requested_sara_settings():
    from voice_service.app import create_voice_service

    engine = FakePiperEngine()
    app = create_voice_service(engine=engine, service_token="secret")
    client = TestClient(app)

    response = client.post(
        "/synthesize",
        headers={"X-SARA-VOICE-TOKEN": "secret"},
        json={
            "text": "hello",
            "length_scale": 1.08,
            "noise_scale": 0.55,
            "noise_w_scale": 0.70,
            "volume": 0.95,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content == b"RIFFpiper-wav"
    assert engine.calls == [
        {
            "text": "hello",
            "length_scale": 1.08,
            "noise_scale": 0.55,
            "noise_w_scale": 0.70,
            "volume": 0.95,
        }
    ]


def test_voice_service_rejects_empty_text():
    from voice_service.app import create_voice_service

    app = create_voice_service(engine=FakePiperEngine(), service_token="secret")
    client = TestClient(app)

    response = client.post(
        "/synthesize",
        headers={"X-SARA-VOICE-TOKEN": "secret"},
        json={"text": ""},
    )
    assert response.status_code == 422


def test_voice_service_health_reports_ready_engine():
    from voice_service.app import create_voice_service

    app = create_voice_service(engine=FakePiperEngine(), service_token="secret")
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"alive": True, "ready": True, "model_id": "en_GB-cori-high"}


def test_cori_model_hash_is_pinned():
    from voice_service.app import EXPECTED_MODEL_SHA256

    assert EXPECTED_MODEL_SHA256 == "470b4dd634c98f8a4850d7626ffc3dfc90774628eeef6605a6dd8f88f30a5903"


def test_model_identity_rejects_non_cori_filename(tmp_path):
    from voice_service.app import _validate_model_identity

    model = tmp_path / "other-voice.onnx"
    model.write_bytes(b"not-cori")
    with pytest.raises(RuntimeError, match="en_GB-cori-high.onnx"):
        _validate_model_identity(model)


def test_model_identity_rejects_wrong_cori_digest(tmp_path):
    from voice_service.app import _validate_model_identity

    model = tmp_path / "en_GB-cori-high.onnx"
    model.write_bytes(b"tampered-model")
    with pytest.raises(RuntimeError, match="SHA-256"):
        _validate_model_identity(model)


def test_model_identity_accepts_matching_digest(tmp_path, monkeypatch):
    import voice_service.app as voice_app

    model = tmp_path / "en_GB-cori-high.onnx"
    model.write_bytes(b"test-cori-model")
    monkeypatch.setattr(voice_app, "EXPECTED_MODEL_SHA256", hashlib.sha256(model.read_bytes()).hexdigest())

    voice_app._validate_model_identity(model)
