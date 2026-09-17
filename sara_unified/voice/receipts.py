from __future__ import annotations

import hashlib
import wave
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO

from .controls import SynthesisControls
from .profile import SARA_VOICE_PROFILE
from .pronunciation import PronunciationDictionary


@dataclass(frozen=True)
class AudioReceipt:
    receipt_id: str
    job_id: str
    segment_id: str
    profile_id: str
    model_id: str
    source_response_sha256: str
    segment_text_sha256: str
    transformed_segment_text_sha256: str
    audio_sha256: str
    audio_bytes: int
    wav_channels: int | None
    wav_frame_rate: int | None
    wav_duration_seconds: float | None
    speech_rate: str
    speech_control_digest: str
    pronunciation_dictionary_id: str
    pronunciation_dictionary_version: str
    pronunciation_dictionary_sha256: str
    voice_service_url_hash: str
    source_commit_sha: str
    deployment_id: str
    duration_ms: int
    created_at: str

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


def _wav_metadata(audio: bytes) -> tuple[int | None, int | None, float | None]:
    try:
        with wave.open(BytesIO(audio), "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            duration = round(frames / frame_rate, 3) if frame_rate else None
            return wav_file.getnchannels(), frame_rate, duration
    except (EOFError, wave.Error):
        return None, None, None


def build_audio_receipt(
    *,
    job_id: str,
    segment_id: str,
    source_response_sha256: str,
    segment_text: str,
    transformed_segment_text: str,
    audio: bytes,
    speech_rate: str,
    controls: SynthesisControls,
    dictionary: PronunciationDictionary,
    source_commit_sha: str,
    deployment_id: str,
    voice_service_url: str,
    duration_ms: int,
) -> AudioReceipt:
    channels, frame_rate, wav_duration = _wav_metadata(audio)
    audio_sha256 = hashlib.sha256(audio).hexdigest()
    return AudioReceipt(
        receipt_id=f"voice-receipt-{job_id}-{segment_id}",
        job_id=job_id,
        segment_id=segment_id,
        profile_id=SARA_VOICE_PROFILE.profile_id,
        model_id=SARA_VOICE_PROFILE.model_id,
        source_response_sha256=source_response_sha256,
        segment_text_sha256=hashlib.sha256(segment_text.encode("utf-8")).hexdigest(),
        transformed_segment_text_sha256=hashlib.sha256(transformed_segment_text.encode("utf-8")).hexdigest(),
        audio_sha256=audio_sha256,
        audio_bytes=len(audio),
        wav_channels=channels,
        wav_frame_rate=frame_rate,
        wav_duration_seconds=wav_duration,
        speech_rate=speech_rate,
        speech_control_digest=controls.digest,
        pronunciation_dictionary_id=dictionary.dictionary_id,
        pronunciation_dictionary_version=dictionary.version,
        pronunciation_dictionary_sha256=dictionary.sha256,
        voice_service_url_hash=hashlib.sha256(voice_service_url.encode("utf-8")).hexdigest(),
        source_commit_sha=source_commit_sha,
        deployment_id=deployment_id,
        duration_ms=duration_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
