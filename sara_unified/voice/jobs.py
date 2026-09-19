from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from .controls import speech_controls_for
from .pronunciation import PronunciationDictionary
from .receipts import AudioReceipt, build_audio_receipt
from .segmenting import VoiceSegment, split_sentences

VoiceJobStatus = Literal["pending", "running", "completed", "stopped", "failed"]


@dataclass
class VoiceJob:
    job_id: str
    status: VoiceJobStatus
    source_response_sha256: str
    segments: list[VoiceSegment]
    receipts: list[AudioReceipt] = field(default_factory=list)
    audio_segments: list[bytes] = field(default_factory=list)
    transcript: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    stop_requested_at: str | None = None

    def public_dict(self, *, include_transcript: bool = False) -> dict[str, object]:
        data = {
            "job_id": self.job_id,
            "status": self.status,
            "source_response_sha256": self.source_response_sha256,
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "status": "completed"
                    if any(receipt.segment_id == segment.segment_id for receipt in self.receipts)
                    else self.status,
                    "text_sha256": segment.text_sha256,
                    "character_count": segment.character_count,
                }
                for segment in self.segments
            ],
            "receipt_ids": [receipt.receipt_id for receipt in self.receipts],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "stop_requested_at": self.stop_requested_at,
            "error": self.error,
        }
        if include_transcript and self.transcript is not None:
            data["transcript"] = self.transcript
        return data


class VoiceJobManager:
    def __init__(
        self,
        *,
        voice_client,
        source_commit_sha: str,
        deployment_id: str,
        voice_service_url: str,
        dictionary: PronunciationDictionary | None = None,
    ):
        self.voice_client = voice_client
        self.source_commit_sha = source_commit_sha
        self.deployment_id = deployment_id
        self.voice_service_url = voice_service_url
        self.dictionary = dictionary or PronunciationDictionary.default()
        self.jobs: dict[str, VoiceJob] = {}

    def start_job(
        self,
        *,
        text: str,
        speech_rate: str = "normal",
        preserve_transcript: bool = False,
        return_audio: str = "none",
    ) -> VoiceJob:
        if return_audio not in {"none", "segments"}:
            raise ValueError("unsupported return_audio")
        speech_controls_for(speech_rate)
        cleaned = text.strip()
        segments = split_sentences(cleaned)
        job = VoiceJob(
            job_id=f"voice-job-{uuid.uuid4()}",
            status="pending",
            source_response_sha256=hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
            segments=segments,
            transcript=cleaned if preserve_transcript else None,
        )
        self.jobs[job.job_id] = job
        return job

    def create_job(
        self,
        *,
        text: str,
        speech_rate: str = "normal",
        preserve_transcript: bool = False,
        return_audio: str = "none",
    ) -> VoiceJob:
        job = self.start_job(
            text=text,
            speech_rate=speech_rate,
            preserve_transcript=preserve_transcript,
            return_audio=return_audio,
        )
        return self.run_job(job.job_id, speech_rate=speech_rate, return_audio=return_audio)

    def run_job(self, job_id: str, *, speech_rate: str = "normal", return_audio: str = "none") -> VoiceJob:
        job = self.jobs[job_id]
        controls = speech_controls_for(speech_rate)
        job.status = "running"
        for segment in job.segments:
            if job.stop_requested_at:
                job.status = "stopped"
                break
            pronunciation = self.dictionary.apply(segment.text)
            started = time.perf_counter()
            try:
                audio = self.voice_client.synthesize_with_controls(pronunciation.text, controls)
            except Exception as exc:
                job.status = "failed"
                job.error = type(exc).__name__
                job.completed_at = datetime.now(timezone.utc).isoformat()
                return job
            duration_ms = int((time.perf_counter() - started) * 1000)
            receipt = build_audio_receipt(
                job_id=job.job_id,
                segment_id=segment.segment_id,
                source_response_sha256=job.source_response_sha256,
                segment_text=segment.text,
                transformed_segment_text=pronunciation.text,
                audio=audio,
                speech_rate=speech_rate,
                controls=controls,
                dictionary=self.dictionary,
                source_commit_sha=self.source_commit_sha,
                deployment_id=self.deployment_id,
                voice_service_url=self.voice_service_url,
                duration_ms=duration_ms,
            )
            job.receipts.append(receipt)
            if return_audio == "segments":
                job.audio_segments.append(audio)
        if job.status == "running":
            job.status = "completed"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        return job

    def get_job(self, job_id: str) -> VoiceJob | None:
        return self.jobs.get(job_id)

    def stop_job(self, job_id: str) -> VoiceJob:
        job = self.jobs[job_id]
        if job.stop_requested_at is None:
            job.stop_requested_at = datetime.now(timezone.utc).isoformat()
        if job.status in {"pending", "running"}:
            job.status = "stopped"
        return job
