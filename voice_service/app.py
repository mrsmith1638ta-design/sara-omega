from __future__ import annotations

import hashlib
import io
import os
import secrets
import wave
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field


MODEL_ID = "en_GB-cori-high"
EXPECTED_MODEL_FILENAME = f"{MODEL_ID}.onnx"
EXPECTED_MODEL_SHA256 = "470b4dd634c98f8a4850d7626ffc3dfc90774628eeef6605a6dd8f88f30a5903"


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    length_scale: float = Field(default=1.08, gt=0.0, le=4.0)
    noise_scale: float = Field(default=0.55, ge=0.0, le=2.0)
    noise_w_scale: float = Field(default=0.70, ge=0.0, le=2.0)
    volume: float = Field(default=0.95, gt=0.0, le=2.0)


class VoiceEngine(Protocol):
    def synthesize(
        self,
        text: str,
        *,
        length_scale: float,
        noise_scale: float,
        noise_w_scale: float,
        volume: float,
    ) -> bytes: ...


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_model_identity(model: Path) -> None:
    if model.name != EXPECTED_MODEL_FILENAME:
        raise RuntimeError(f"Piper model must be {EXPECTED_MODEL_FILENAME}")
    if not model.is_file():
        raise RuntimeError("Piper model file is required")
    actual_digest = _file_sha256(model)
    if not secrets.compare_digest(actual_digest, EXPECTED_MODEL_SHA256):
        raise RuntimeError("Piper model SHA-256 does not match the approved Cori model")


class PiperEngine:
    def __init__(self, model_path: str):
        from piper import PiperVoice, SynthesisConfig

        self._synthesis_config = SynthesisConfig
        self._voice = PiperVoice.load(model_path, f"{model_path}.json")

    def synthesize(
        self,
        text: str,
        *,
        length_scale: float,
        noise_scale: float,
        noise_w_scale: float,
        volume: float,
    ) -> bytes:
        config = self._synthesis_config(
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w_scale=noise_w_scale,
            volume=volume,
        )
        output = io.BytesIO()
        with wave.open(output, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file, config)
        return output.getvalue()


def _load_engine_from_env() -> VoiceEngine:
    model_path = os.getenv("PIPER_MODEL_PATH", "").strip()
    if not model_path:
        raise RuntimeError("Piper model path is required")
    model = Path(model_path)
    _validate_model_identity(model)
    config = Path(f"{model_path}.json")
    if not config.is_file():
        raise RuntimeError("Piper matching .onnx.json configuration is required")
    return PiperEngine(str(model))


def create_voice_service(*, engine: VoiceEngine | None = None, service_token: str | None = None) -> FastAPI:
    token = (service_token if service_token is not None else os.getenv("SARA_VOICE_SERVICE_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("SARA voice service token is required")

    voice_engine = engine or _load_engine_from_env()
    app = FastAPI(title="SARA OMEGA Piper Voice Service", version="1.0.0")

    @app.get("/health")
    def health():
        return {"alive": True, "ready": True, "model_id": MODEL_ID}

    @app.post("/synthesize")
    def synthesize(
        request: SynthesisRequest,
        x_sara_voice_token: str | None = Header(default=None),
    ):
        if x_sara_voice_token is None or not secrets.compare_digest(x_sara_voice_token, token):
            raise HTTPException(status_code=401, detail="unauthorized")
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="voice text must not be empty")
        audio = voice_engine.synthesize(
            text,
            length_scale=request.length_scale,
            noise_scale=request.noise_scale,
            noise_w_scale=request.noise_w_scale,
            volume=request.volume,
        )
        if not audio:
            raise HTTPException(status_code=502, detail="Piper returned empty audio")
        return Response(content=audio, media_type="audio/wav")

    return app


def create_default_app() -> FastAPI:
    return create_voice_service()
