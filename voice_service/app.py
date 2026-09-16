from __future__ import annotations

import io
import os
import wave
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field


MODEL_ID = "en_GB-cori-high"


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
    config = Path(f"{model_path}.json")
    if not model.is_file() or not config.is_file():
        raise RuntimeError("Piper model and matching .onnx.json configuration are required")
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
        if x_sara_voice_token != token:
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
