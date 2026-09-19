# SARA OMEGA Voice 1.1 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement SARA Voice 1.1 as an owner/internal-only hardening release with segmented speech jobs, stop support, pronunciation handling, bounded speech-rate presets, audio receipts, benchmarks, and restart/persistence evidence while preserving Voice 1.0 evidence unchanged.

**Architecture:** Keep Piper isolated in `voice_service/` and add a SARA-owned orchestration layer under `sara_unified.voice`. Production `main.py` exposes owner-only Voice 1.1 routes that call the orchestration layer, while public accessibility routes remain gated off for Voice 1.1A.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, HTTPX, pytest, Railway.

**Spec:** `docs/superpowers/specs/2026-09-17-voice-1-1-hardening-design.md`

## Global Constraints

- Voice 1.0 acceptance artifacts under `outputs/` must not be edited.
- Main SARA runtime must not import `piper-tts`.
- Piper runtime remains isolated under `voice_service/`.
- Owner authority is required for production Voice 1.1 routes.
- `GPT_ACTION_TOKEN` must not authorize Voice 1.1 jobs, receipts, stops, or restart checks.
- Voice 1.1 public accessibility routes must stay disabled or absent.
- Callers must not provide arbitrary model IDs, model paths, filesystem paths, service URLs, executable args, or raw Piper parameters.
- Speech-rate controls are preset-only: `slower`, `normal`, `faster`.
- Transcript preservation defaults to false and is explicit when enabled.
- Receipts must not contain secret values.
- Restart/persistence acceptance must prove valid model reuse without weakening filename or SHA-256 validation.

---

### Task 1: Voice 1.1 Core Contracts

**Files:**
- Create: `sara_unified/voice/segmenting.py`
- Create: `sara_unified/voice/controls.py`
- Create: `sara_unified/voice/pronunciation.py`
- Create: `sara_unified/voice/receipts.py`
- Modify: `sara_unified/voice/__init__.py`
- Test: `tests/test_voice_1_1_core.py`

**Interfaces:**
- Produces: `split_sentences(text: str, *, max_segments: int = 64, max_segment_characters: int = 600) -> list[VoiceSegment]`
- Produces: `SpeechRate` enum and `speech_controls_for(rate: SpeechRate | str) -> SynthesisControls`
- Produces: `PronunciationDictionary.apply(text: str) -> PronunciationResult`
- Produces: `build_audio_receipt(...) -> AudioReceipt`

- [ ] **Step 1: Write failing core tests**

Create `tests/test_voice_1_1_core.py`:

```python
import hashlib

import pytest


def test_sentence_segmentation_is_deterministic_and_digest_bound():
    from sara_unified.voice.segmenting import split_sentences

    segments = split_sentences("SARA is online. Voice 1.1 is ready!", max_segments=8)

    assert [segment.segment_id for segment in segments] == ["seg-0001", "seg-0002"]
    assert [segment.text for segment in segments] == ["SARA is online.", "Voice 1.1 is ready!"]
    assert segments[0].text_sha256 == hashlib.sha256(b"SARA is online.").hexdigest()


def test_sentence_segmentation_rejects_empty_and_excessive_segments():
    from sara_unified.voice.segmenting import split_sentences

    with pytest.raises(ValueError, match="voice text must not be empty"):
        split_sentences("   ")
    with pytest.raises(ValueError, match="too many voice segments"):
        split_sentences("One. Two. Three.", max_segments=2)


def test_speech_rate_presets_are_bounded_and_no_arbitrary_float_is_accepted():
    from sara_unified.voice.controls import speech_controls_for

    assert speech_controls_for("slower").length_scale == 1.16
    assert speech_controls_for("normal").length_scale == 1.08
    assert speech_controls_for("faster").length_scale == 1.00
    with pytest.raises(ValueError, match="unsupported speech rate"):
        speech_controls_for("1.37")


def test_pronunciation_dictionary_applies_ordered_rules_and_exposes_digest():
    from sara_unified.voice.pronunciation import PronunciationDictionary, PronunciationRule

    dictionary = PronunciationDictionary(
        dictionary_id="sara-default",
        version="2026.09.17",
        rules=(
            PronunciationRule(match="SARA", replacement="Sarah"),
            PronunciationRule(match="OMEGA", replacement="Omega"),
        ),
    )

    result = dictionary.apply("SARA OMEGA is live.")

    assert result.text == "Sarah Omega is live."
    assert result.dictionary_id == "sara-default"
    assert result.dictionary_version == "2026.09.17"
    assert len(result.dictionary_sha256) == 64
    assert result.applied_rules == ["SARA", "OMEGA"]


def test_audio_receipt_binds_source_segment_audio_controls_and_dictionary():
    from sara_unified.voice.controls import speech_controls_for
    from sara_unified.voice.pronunciation import PronunciationDictionary
    from sara_unified.voice.receipts import build_audio_receipt

    dictionary = PronunciationDictionary.default()
    controls = speech_controls_for("normal")

    receipt = build_audio_receipt(
        job_id="voice-job-1",
        segment_id="seg-0001",
        source_response_sha256="a" * 64,
        segment_text="SARA is live.",
        transformed_segment_text="Sarah is live.",
        audio=b"RIFFaudio",
        speech_rate="normal",
        controls=controls,
        dictionary=dictionary,
        source_commit_sha="30c1f606092b6d4043413a185d8e0ac8d3458de2",
        deployment_id="unit-deployment",
        voice_service_url="http://sara-piper-voice.railway.internal:8080",
        duration_ms=25,
    )

    assert receipt.profile_id == "sara_elegant_british_v1"
    assert receipt.model_id == "en_GB-cori-high"
    assert receipt.audio_sha256 == hashlib.sha256(b"RIFFaudio").hexdigest()
    assert receipt.voice_service_url_hash != "http://sara-piper-voice.railway.internal:8080"
    assert "token" not in repr(receipt).lower()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_voice_1_1_core.py`

Expected: FAIL with import errors for new modules.

- [ ] **Step 3: Implement segmentation**

Create `sara_unified/voice/segmenting.py`:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceSegment:
    segment_id: str
    index: int
    text: str
    text_sha256: str
    character_count: int


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def split_sentences(
    text: str,
    *,
    max_segments: int = 64,
    max_segment_characters: int = 600,
) -> list[VoiceSegment]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise ValueError("voice text must not be empty")
    if max_segments <= 0:
        raise ValueError("max_segments must be positive")
    if max_segment_characters <= 0:
        raise ValueError("max_segment_characters must be positive")

    raw_segments = [part.strip() for part in _SENTENCE_BOUNDARY.split(cleaned) if part.strip()]
    expanded: list[str] = []
    for raw in raw_segments:
        if len(raw) <= max_segment_characters:
            expanded.append(raw)
            continue
        words = raw.split()
        current: list[str] = []
        current_length = 0
        for word in words:
            next_length = current_length + len(word) + (1 if current else 0)
            if current and next_length > max_segment_characters:
                expanded.append(" ".join(current))
                current = [word]
                current_length = len(word)
            else:
                current.append(word)
                current_length = next_length
        if current:
            expanded.append(" ".join(current))

    if len(expanded) > max_segments:
        raise ValueError("too many voice segments")

    return [
        VoiceSegment(
            segment_id=f"seg-{index:04d}",
            index=index,
            text=segment,
            text_sha256=hashlib.sha256(segment.encode("utf-8")).hexdigest(),
            character_count=len(segment),
        )
        for index, segment in enumerate(expanded, start=1)
    ]
```

- [ ] **Step 4: Implement speech controls**

Create `sara_unified/voice/controls.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum


class SpeechRate(StrEnum):
    SLOWER = "slower"
    NORMAL = "normal"
    FASTER = "faster"


@dataclass(frozen=True)
class SynthesisControls:
    speech_rate: SpeechRate
    length_scale: float
    noise_scale: float = 0.55
    noise_w_scale: float = 0.70
    volume: float = 0.95

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode("utf-8")).hexdigest()


_CONTROLS = {
    SpeechRate.SLOWER: SynthesisControls(SpeechRate.SLOWER, length_scale=1.16),
    SpeechRate.NORMAL: SynthesisControls(SpeechRate.NORMAL, length_scale=1.08),
    SpeechRate.FASTER: SynthesisControls(SpeechRate.FASTER, length_scale=1.00),
}


def speech_controls_for(rate: SpeechRate | str) -> SynthesisControls:
    try:
        normalized = rate if isinstance(rate, SpeechRate) else SpeechRate(str(rate))
    except ValueError as exc:
        raise ValueError("unsupported speech rate") from exc
    return _CONTROLS[normalized]
```

- [ ] **Step 5: Implement pronunciation dictionary**

Create `sara_unified/voice/pronunciation.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PronunciationRule:
    match: str
    replacement: str


@dataclass(frozen=True)
class PronunciationResult:
    text: str
    dictionary_id: str
    dictionary_version: str
    dictionary_sha256: str
    applied_rules: list[str]


@dataclass(frozen=True)
class PronunciationDictionary:
    dictionary_id: str
    version: str
    rules: tuple[PronunciationRule, ...] = ()
    max_output_characters: int = 5000

    @classmethod
    def default(cls) -> "PronunciationDictionary":
        return cls(
            dictionary_id="sara-default",
            version="2026.09.17",
            rules=(
                PronunciationRule("SARA", "Sarah"),
                PronunciationRule("SARA OMEGA", "Sarah Omega"),
            ),
        )

    @property
    def sha256(self) -> str:
        payload = {
            "dictionary_id": self.dictionary_id,
            "version": self.version,
            "rules": [asdict(rule) for rule in self.rules],
            "max_output_characters": self.max_output_characters,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def apply(self, text: str) -> PronunciationResult:
        transformed = text
        applied: list[str] = []
        for rule in self.rules:
            if rule.match in transformed:
                transformed = transformed.replace(rule.match, rule.replacement)
                applied.append(rule.match)
        if len(transformed) > self.max_output_characters:
            raise ValueError("pronunciation output exceeds maximum length")
        return PronunciationResult(
            text=transformed,
            dictionary_id=self.dictionary_id,
            dictionary_version=self.version,
            dictionary_sha256=self.sha256,
            applied_rules=applied,
        )
```

- [ ] **Step 6: Implement audio receipts**

Create `sara_unified/voice/receipts.py`:

```python
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
    except wave.Error:
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
```

- [ ] **Step 7: Export interfaces**

Modify `sara_unified/voice/__init__.py` to export `VoiceSegment`, `split_sentences`, `SpeechRate`, `SynthesisControls`, `speech_controls_for`, `PronunciationDictionary`, `PronunciationRule`, `AudioReceipt`, and `build_audio_receipt`.

- [ ] **Step 8: Run focused tests**

Run: `pytest -q tests/test_voice_1_1_core.py`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add sara_unified/voice tests/test_voice_1_1_core.py
git commit -m "feat: add Voice 1.1 core contracts"
```

---

### Task 2: Voice Job Orchestration

**Files:**
- Create: `sara_unified/voice/jobs.py`
- Modify: `sara_unified/voice/client.py`
- Test: `tests/test_voice_1_1_jobs.py`

**Interfaces:**
- Consumes: `split_sentences`, `speech_controls_for`, `PronunciationDictionary`, `build_audio_receipt`.
- Produces: `VoiceJobManager.create_job(...) -> VoiceJob`
- Produces: `VoiceJobManager.stop_job(job_id: str) -> VoiceJob`
- Produces: `PiperVoiceClient.synthesize_with_controls(text: str, controls: SynthesisControls) -> bytes`

- [ ] **Step 1: Write failing job orchestration tests**

Create `tests/test_voice_1_1_jobs.py`:

```python
class FakeVoiceClient:
    def __init__(self, stop_after_first=False):
        self.calls = []
        self.stop_after_first = stop_after_first
        self.manager = None
        self.job_id = None

    def synthesize_with_controls(self, text, controls):
        self.calls.append((text, controls.length_scale))
        if self.stop_after_first and len(self.calls) == 1:
            self.manager.stop_job(self.job_id)
        return b"RIFFfake-segment"


def test_voice_job_creates_segment_receipts_without_raw_text_by_default():
    from sara_unified.voice.jobs import VoiceJobManager

    fake = FakeVoiceClient()
    manager = VoiceJobManager(
        voice_client=fake,
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )

    job = manager.create_job(
        text="SARA is online. Voice 1.1 is ready.",
        speech_rate="normal",
        preserve_transcript=False,
        return_audio="segments",
    )

    assert job.status == "completed"
    assert len(job.segments) == 2
    assert len(job.receipts) == 2
    assert len(job.audio_segments) == 2
    assert "SARA is online" not in repr(job.public_dict(include_transcript=False))
    assert fake.calls[0][0] == "Sarah is online."


def test_voice_job_preserves_transcript_only_when_requested():
    from sara_unified.voice.jobs import VoiceJobManager

    manager = VoiceJobManager(
        voice_client=FakeVoiceClient(),
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )

    hidden = manager.create_job(text="Private sentence.", preserve_transcript=False)
    preserved = manager.create_job(text="Preserved sentence.", preserve_transcript=True)

    assert hidden.transcript is None
    assert preserved.transcript == "Preserved sentence."


def test_voice_job_stop_is_idempotent_and_prevents_later_segments():
    from sara_unified.voice.jobs import VoiceJobManager

    fake = FakeVoiceClient(stop_after_first=True)
    manager = VoiceJobManager(
        voice_client=fake,
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )
    fake.manager = manager

    job = manager.start_job(
        text="First sentence. Second sentence. Third sentence.",
        speech_rate="normal",
        preserve_transcript=False,
        return_audio="none",
    )
    fake.job_id = job.job_id
    completed = manager.run_job(job.job_id)
    stopped_again = manager.stop_job(job.job_id)

    assert completed.status == "stopped"
    assert stopped_again.status == "stopped"
    assert len(fake.calls) == 1
    assert completed.stop_requested_at is not None


def test_voice_job_rejects_unsupported_audio_return_mode():
    import pytest
    from sara_unified.voice.jobs import VoiceJobManager

    manager = VoiceJobManager(
        voice_client=FakeVoiceClient(),
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )

    with pytest.raises(ValueError, match="unsupported return_audio"):
        manager.create_job(text="Hello.", return_audio="wav_archive")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_voice_1_1_jobs.py`

Expected: FAIL with import error for `sara_unified.voice.jobs`.

- [ ] **Step 3: Extend Piper client with controlled synthesis**

Modify `sara_unified/voice/client.py`:

```python
from .controls import SynthesisControls


def _post_synthesis(self, text: str, payload: dict[str, object]) -> bytes:
    try:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.service_url}/synthesize",
                headers={"X-SARA-VOICE-TOKEN": self.service_token},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise VoiceSynthesisError("Piper service unavailable") from exc
    if response.status_code != 200:
        raise VoiceSynthesisError(f"Piper service returned HTTP {response.status_code}")
    if not response.headers.get("content-type", "").lower().startswith("audio/wav"):
        raise VoiceSynthesisError("Piper service returned a non-WAV response")
    if not response.content:
        raise VoiceSynthesisError("Piper service returned empty audio")
    return bytes(response.content)
```

Refactor existing `synthesize()` to call `_post_synthesis()` with the fixed Voice 1.0 profile payload. Add:

```python
def synthesize_with_controls(self, text: str, controls: SynthesisControls) -> bytes:
    return self._post_synthesis(
        text,
        {
            "text": text,
            "length_scale": controls.length_scale,
            "noise_scale": controls.noise_scale,
            "noise_w_scale": controls.noise_w_scale,
            "volume": controls.volume,
        },
    )
```

- [ ] **Step 4: Implement job manager**

Create `sara_unified/voice/jobs.py`:

```python
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
                    "status": "completed" if any(r.segment_id == segment.segment_id for r in self.receipts) else self.status,
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
        segments = split_sentences(text)
        job = VoiceJob(
            job_id=f"voice-job-{uuid.uuid4()}",
            status="pending",
            source_response_sha256=hashlib.sha256(text.strip().encode("utf-8")).hexdigest(),
            segments=segments,
            transcript=text.strip() if preserve_transcript else None,
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
```

- [ ] **Step 5: Run job tests and Voice 1.0 client tests**

Run: `pytest -q tests/test_voice_1_1_jobs.py tests/test_voice_synthesis.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sara_unified/voice/client.py sara_unified/voice/jobs.py tests/test_voice_1_1_jobs.py
git commit -m "feat: add Voice 1.1 job orchestration"
```

---

### Task 3: Production Owner/Internal Voice 1.1 Routes

**Files:**
- Modify: `sara_unified/config.py`
- Modify: `sara_unified/api/schemas.py`
- Modify: `main.py`
- Test: `tests/test_production_voice_1_1.py`

**Interfaces:**
- Produces: `SARA_VOICE_1_1_ENABLED`
- Produces: `POST /v1/voice/jobs`
- Produces: `GET /v1/voice/jobs/{job_id}`
- Produces: `POST /v1/voice/jobs/{job_id}/stop`
- Produces: `GET /v1/voice/jobs/{job_id}/receipts`
- Produces: gated accessibility route behavior

- [ ] **Step 1: Write failing production route tests**

Create `tests/test_production_voice_1_1.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_production_voice_1_1.py`

Expected: FAIL because routes and settings do not exist.

- [ ] **Step 3: Add settings**

Modify `sara_unified/config.py`:

```python
voice_1_1_enabled: bool = False
voice_accessibility_public_enabled: bool = False
```

In `Settings.from_env()`, parse:

```python
voice_1_1_enabled=os.getenv("SARA_VOICE_1_1_ENABLED", "false").lower() == "true",
voice_accessibility_public_enabled=os.getenv("SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED", "false").lower() == "true",
```

- [ ] **Step 4: Add request schemas**

Modify `sara_unified/api/schemas.py`:

```python
class VoiceJobRequest(BaseModel):
    text: str = Field(min_length=1)
    speech_rate: str = Field(default="normal")
    preserve_transcript: bool = False
    return_audio: str = Field(default="none")
```

- [ ] **Step 5: Add production route helpers**

Modify `main.py` imports:

```python
from sara_unified.api.schemas import VoiceJobRequest, VoiceSynthesisRequest
from sara_unified.voice.jobs import VoiceJobManager
```

Add global:

```python
_voice_1_1_job_manager: VoiceJobManager | None = None
```

Add helpers:

```python
def require_owner(req: Request) -> None:
    if not authorize(req):
        raise HTTPException(401, "Unauthorized")
    if authorize(req) != "owner":
        raise HTTPException(403, "Owner only")


def get_voice_1_1_job_manager(settings: Settings) -> VoiceJobManager | None:
    global _voice_1_1_job_manager
    if _voice_1_1_job_manager is not None:
        return _voice_1_1_job_manager
    voice_client = get_piper_voice_client(settings)
    if voice_client is None:
        return None
    _voice_1_1_job_manager = VoiceJobManager(
        voice_client=voice_client,
        source_commit_sha=os.getenv("SARA_SOURCE_COMMIT_SHA", ""),
        deployment_id=os.getenv("RAILWAY_DEPLOYMENT_ID", ""),
        voice_service_url=settings.piper_service_url,
    )
    return _voice_1_1_job_manager
```

- [ ] **Step 6: Add production routes**

Modify `main.py` after the Voice 1.0 routes:

```python
@app.post("/v1/voice/jobs")
def create_voice_job(payload: VoiceJobRequest, req: Request):
    require_owner(req)
    settings = Settings.from_env()
    if not settings.voice_1_1_enabled:
        raise HTTPException(503, "Voice 1.1 disabled")
    manager = get_voice_1_1_job_manager(settings)
    if manager is None:
        raise HTTPException(503, "Voice synthesis unavailable")
    try:
        job = manager.create_job(
            text=payload.text,
            speech_rate=payload.speech_rate,
            preserve_transcript=payload.preserve_transcript,
            return_audio=payload.return_audio,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return job.public_dict(include_transcript=payload.preserve_transcript)


@app.get("/v1/voice/jobs/{job_id}")
def get_voice_job(job_id: str, req: Request):
    require_owner(req)
    settings = Settings.from_env()
    manager = get_voice_1_1_job_manager(settings)
    if manager is None or manager.get_job(job_id) is None:
        raise HTTPException(404, "voice job not found")
    return manager.get_job(job_id).public_dict(include_transcript=False)


@app.post("/v1/voice/jobs/{job_id}/stop")
def stop_voice_job(job_id: str, req: Request):
    require_owner(req)
    settings = Settings.from_env()
    manager = get_voice_1_1_job_manager(settings)
    if manager is None or manager.get_job(job_id) is None:
        raise HTTPException(404, "voice job not found")
    return manager.stop_job(job_id).public_dict(include_transcript=False)


@app.get("/v1/voice/jobs/{job_id}/receipts")
def get_voice_job_receipts(job_id: str, req: Request):
    require_owner(req)
    settings = Settings.from_env()
    manager = get_voice_1_1_job_manager(settings)
    if manager is None or manager.get_job(job_id) is None:
        raise HTTPException(404, "voice job not found")
    job = manager.get_job(job_id)
    return {"job_id": job_id, "receipts": [receipt.public_dict() for receipt in job.receipts]}


@app.post("/v1/accessibility/voice/jobs")
def accessibility_voice_jobs_gated():
    raise HTTPException(404, "Voice accessibility public API is not enabled for Voice 1.1")
```

- [ ] **Step 7: Run route tests**

Run: `pytest -q tests/test_production_voice_1_1.py tests/test_production_piper_voice.py`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add main.py sara_unified/config.py sara_unified/api/schemas.py tests/test_production_voice_1_1.py
git commit -m "feat: expose owner-only Voice 1.1 routes"
```

---

### Task 4: Voice Service Persistence Metadata

**Files:**
- Modify: `voice_service/bootstrap.py`
- Modify: `voice_service/app.py`
- Test: `tests/test_voice_bootstrap.py`
- Test: `tests/test_voice_service.py`

**Interfaces:**
- Produces: `BootstrapResult(model_path, config_path, model_sha256, reused_existing)`
- Produces: `/health` metadata with `model_sha256`, `model_path`, and `reused_existing_model`

- [ ] **Step 1: Write failing bootstrap metadata tests**

Extend `tests/test_voice_bootstrap.py`:

```python
def test_bootstrap_reports_reused_existing_persistent_assets(tmp_path, monkeypatch):
    import hashlib
    import voice_service.bootstrap as bootstrap

    model = tmp_path / "en_GB-cori-high.onnx"
    config = tmp_path / "en_GB-cori-high.onnx.json"
    model.write_bytes(b"existing-cori")
    config.write_text("{}", encoding="utf-8")
    expected = hashlib.sha256(model.read_bytes()).hexdigest()
    monkeypatch.setattr(bootstrap, "EXPECTED_MODEL_SHA256", expected)

    result = bootstrap.ensure_cori_model(tmp_path, downloader=lambda *_: (_ for _ in ()).throw(AssertionError()))

    assert result.model_path == model
    assert result.config_path == config
    assert result.model_sha256 == expected
    assert result.reused_existing is True
```

Extend `tests/test_voice_service.py`:

```python
def test_voice_service_health_includes_model_integrity_metadata():
    from voice_service.app import create_voice_service

    app = create_voice_service(
        engine=FakePiperEngine(),
        service_token="secret",
        model_integrity={
            "model_sha256": "a" * 64,
            "model_path": "/models/en_GB-cori-high.onnx",
            "reused_existing_model": True,
        },
    )
    client = TestClient(app)

    body = client.get("/health").json()

    assert body["model_sha256"] == "a" * 64
    assert body["model_path"] == "/models/en_GB-cori-high.onnx"
    assert body["reused_existing_model"] is True
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_voice_bootstrap.py tests/test_voice_service.py`

Expected: FAIL because `ensure_cori_model()` returns a tuple and `create_voice_service()` lacks `model_integrity`.

- [ ] **Step 3: Implement bootstrap result**

Modify `voice_service/bootstrap.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class BootstrapResult:
    model_path: Path
    config_path: Path
    model_sha256: str
    reused_existing: bool
```

Change `ensure_cori_model()` to return `BootstrapResult`. Existing verified files return `reused_existing=True`; downloaded files return `reused_existing=False`.

Update `main()`:

```python
result = ensure_cori_model(model_path.parent)
os.environ["PIPER_MODEL_PATH"] = str(result.model_path)
os.environ["PIPER_MODEL_SHA256"] = result.model_sha256
os.environ["PIPER_MODEL_REUSED_EXISTING"] = "true" if result.reused_existing else "false"
```

- [ ] **Step 4: Implement health metadata**

Modify `voice_service/app.py`:

```python
def _model_integrity_from_env(model_path: str) -> dict[str, object]:
    return {
        "model_sha256": os.getenv("PIPER_MODEL_SHA256", EXPECTED_MODEL_SHA256),
        "model_path": model_path,
        "reused_existing_model": os.getenv("PIPER_MODEL_REUSED_EXISTING", "false").lower() == "true",
    }
```

Change `create_voice_service()` signature:

```python
def create_voice_service(*, engine: VoiceEngine | None = None, service_token: str | None = None, model_integrity: dict[str, object] | None = None) -> FastAPI:
```

Have `/health` return:

```python
return {"alive": True, "ready": True, "model_id": MODEL_ID, **integrity}
```

When loading from env, set integrity from env after `_load_engine_from_env()`.

- [ ] **Step 5: Update tests for previous tuple callers**

Any test that expects `model, config = ensure_cori_model(...)` must read `result.model_path` and `result.config_path`.

- [ ] **Step 6: Run voice service tests**

Run: `pytest -q tests/test_voice_bootstrap.py tests/test_voice_service.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add voice_service/app.py voice_service/bootstrap.py tests/test_voice_bootstrap.py tests/test_voice_service.py
git commit -m "feat: expose Piper model persistence metadata"
```

---

### Task 5: Benchmark And Acceptance Evidence Tools

**Files:**
- Create: `tools/voice_1_1_benchmark.py`
- Create: `tools/voice_1_1_acceptance_probe.py`
- Test: `tests/test_voice_1_1_tools.py`

**Interfaces:**
- Produces: benchmark JSON with latency distribution and thresholds.
- Produces: acceptance JSON that references Voice 1.0 capsule but does not edit it.

- [ ] **Step 1: Write failing tool tests**

Create `tests/test_voice_1_1_tools.py`:

```python
import json


def test_benchmark_summary_computes_latency_percentiles():
    from tools.voice_1_1_benchmark import summarize_latencies

    summary = summarize_latencies([100, 200, 300, 400])

    assert summary["count"] == 4
    assert summary["p50_ms"] == 250
    assert summary["max_ms"] == 400


def test_acceptance_evidence_references_voice_1_0_without_mutating_it(tmp_path):
    from tools.voice_1_1_acceptance_probe import build_acceptance_evidence

    capsule = tmp_path / "voice-1-0.md"
    capsule.write_text("immutable voice 1.0", encoding="utf-8")

    evidence = build_acceptance_evidence(
        voice_1_0_capsule=str(capsule),
        source_commit_sha="implementation-sha",
        deployment_id="deployment-id",
        job_receipt={"job_id": "voice-job-1"},
        benchmark={"count": 1},
        restart_persistence={"reused_existing_model": True},
        road={"production_accepted": True},
    )

    assert evidence["voice_1_0_capsule"] == str(capsule)
    assert evidence["voice_1_0_capsule_sha256"]
    assert evidence["voice_1_1"]["source_commit_sha"] == "implementation-sha"
    assert capsule.read_text(encoding="utf-8") == "immutable voice 1.0"
    assert "secret" not in json.dumps(evidence).lower()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_voice_1_1_tools.py`

Expected: FAIL because tools do not exist.

- [ ] **Step 3: Implement benchmark helper**

Create `tools/voice_1_1_benchmark.py`:

```python
from __future__ import annotations

import math


def percentile(values: list[int], percentile_value: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    rank = (len(ordered) - 1) * percentile_value
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weighted = ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower)
    return int(round(weighted))


def summarize_latencies(latencies_ms: list[int]) -> dict[str, int]:
    return {
        "count": len(latencies_ms),
        "p50_ms": percentile(latencies_ms, 0.50),
        "p95_ms": percentile(latencies_ms, 0.95),
        "p99_ms": percentile(latencies_ms, 0.99),
        "max_ms": max(latencies_ms) if latencies_ms else 0,
    }
```

The executable portion of this tool can be added in the implementation pass after the routes exist. It should call `/v1/voice/jobs` repeatedly with owner auth loaded from Railway env and write to `outputs/sara-omega-voice-1-1-benchmark.json`.

- [ ] **Step 4: Implement acceptance evidence builder**

Create `tools/voice_1_1_acceptance_probe.py`:

```python
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def _file_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_acceptance_evidence(
    *,
    voice_1_0_capsule: str,
    source_commit_sha: str,
    deployment_id: str,
    job_receipt: dict,
    benchmark: dict,
    restart_persistence: dict,
    road: dict,
) -> dict:
    return {
        "evidence_type": "sara-omega-voice-1-1-acceptance",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "voice_1_0_capsule": voice_1_0_capsule,
        "voice_1_0_capsule_sha256": _file_sha256(voice_1_0_capsule),
        "voice_1_1": {
            "source_commit_sha": source_commit_sha,
            "deployment_id": deployment_id,
            "job_receipt": job_receipt,
            "benchmark": benchmark,
            "restart_persistence": restart_persistence,
            "road": road,
        },
        "secret_values_recorded": False,
    }
```

- [ ] **Step 5: Run tool tests**

Run: `pytest -q tests/test_voice_1_1_tools.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/voice_1_1_benchmark.py tools/voice_1_1_acceptance_probe.py tests/test_voice_1_1_tools.py
git commit -m "feat: add Voice 1.1 evidence tools"
```

---

### Task 6: Repository Verification And Production Acceptance Runbook

**Files:**
- Modify: `README.md`
- Create: `docs/voice-1-1-production-acceptance.md`
- Test: existing repository tests.

**Interfaces:**
- Produces: operator runbook for enabling Voice 1.1 internally, running benchmarks, restart/persistence checks, and preserving new evidence without modifying Voice 1.0 artifacts.

- [ ] **Step 1: Document Voice 1.1 internal boundary in README**

Add a short README section after the existing Piper voice section:

```markdown
### Voice 1.1 hardening

Voice 1.1 is an owner/internal-only certification surface. Enable it only with `SARA_VOICE_1_1_ENABLED=true` after the Voice 1.1 implementation has passed repository tests and production acceptance. Public accessibility voice routes remain disabled until a separate Voice 1.1A release gate.
```

- [ ] **Step 2: Create production acceptance runbook**

Create `docs/voice-1-1-production-acceptance.md`:

```markdown
# SARA OMEGA Voice 1.1 Production Acceptance

Voice 1.1 evidence is additive. Do not edit Voice 1.0 evidence files.

## Required Checks

1. Confirm repository tests pass.
2. Confirm `SARA_VOICE_1_1_ENABLED=true` is set only on the owner/internal production service.
3. Confirm `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED` is absent or false.
4. Run an owner/internal segmented job with at least two segments.
5. Retrieve receipts and verify source-response digest, segment digests, audio digests, model ID, profile ID, dictionary digest, and speech-control digest.
6. Run stop/interrupt acceptance.
7. Run benchmark characterization and save JSON under `outputs/`.
8. Restart or redeploy `sara-piper-voice`.
9. Verify `/health` reports the pinned model SHA and `reused_existing_model=true`.
10. Run post-restart synthesis.
11. Verify ROAD production acceptance remains PASS.

## Required Evidence Files

- `outputs/sara-omega-voice-1-1-job-receipts.json`
- `outputs/sara-omega-voice-1-1-benchmark.json`
- `outputs/sara-omega-voice-1-1-restart-persistence.json`
- `outputs/sara-omega-voice-1-1-acceptance-summary.json`
```

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall -q main.py sara_unified voice_service tools
python - <<'PY'
from pathlib import Path
main = Path('requirements.txt').read_text(encoding='utf-8').lower()
assert 'piper-tts' not in main
assert Path('docs/superpowers/specs/2026-09-17-voice-1-1-hardening-design.md').exists()
assert Path('docs/superpowers/plans/2026-09-17-voice-1-1-hardening.md').exists()
PY
```

Expected: all commands succeed.

- [ ] **Step 4: Commit docs**

```bash
git add README.md docs/voice-1-1-production-acceptance.md
git commit -m "docs: add Voice 1.1 production acceptance runbook"
```

---

### Task 7: Deployment And ROAD Evidence Preservation

**Files:**
- Create output only after deployment:
  - `outputs/sara-omega-voice-1-1-job-receipts.json`
  - `outputs/sara-omega-voice-1-1-benchmark.json`
  - `outputs/sara-omega-voice-1-1-restart-persistence.json`
  - `outputs/sara-omega-voice-1-1-acceptance-summary.json`

**Interfaces:**
- Consumes: production owner token through Railway environment only.
- Produces: exact code -> deployment -> segmented-audio receipt chain for Voice 1.1.

- [ ] **Step 1: Push implementation branch or main commit**

Run:

```bash
git status --short --branch
git log -1 --oneline
git push origin main
```

Expected: clean worktree and pushed implementation commit.

- [ ] **Step 2: Deploy SARA core**

Run:

```bash
railway up --service sara-omega --environment production --detach --message "deploy Voice 1.1 hardening <commit-sha>"
railway deployment list --service sara-omega
```

Expected: new `sara-omega` deployment reaches `SUCCESS`.

- [ ] **Step 3: Set final source commit variable**

Run:

```bash
railway variable set --service sara-omega SARA_SOURCE_COMMIT_SHA=<full-implementation-sha>
railway variable set --service sara-omega SARA_VOICE_1_1_ENABLED=true
railway variable set --service sara-omega SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=false
```

Expected: redeploy reaches `SUCCESS`.

- [ ] **Step 4: Run live owner/internal acceptance probes**

Run the acceptance probe using `railway run --service sara-omega` so owner token is never printed:

```bash
railway run --service sara-omega python tools/voice_1_1_acceptance_probe.py
```

Expected:

- segmented job status `completed`
- receipts retrieved
- public accessibility route returns gated `404` or `403`
- unauthenticated Voice 1.1 route returns `401`
- GPT action token route returns `403`
- no secret values written

- [ ] **Step 5: Run benchmark probe**

Run:

```bash
railway run --service sara-omega python tools/voice_1_1_benchmark.py
```

Expected: benchmark JSON saved with latency distribution and no failures beyond defined conservative thresholds.

- [ ] **Step 6: Prove restart/persistence**

Run:

```bash
railway redeploy --service sara-piper-voice
railway deployment list --service sara-piper-voice
railway logs --service sara-piper-voice --deployment --lines 120
```

Expected:

- voice service deployment reaches `SUCCESS`
- logs or health metadata show pinned Cori SHA verification
- metadata shows existing model reuse when the valid `/models` assets exist
- post-restart Voice 1.1 segmented synthesis succeeds

- [ ] **Step 7: Verify ROAD acceptance**

Use ROAD tool:

```text
_get_production_acceptance
_get_blocking_dependencies
```

Expected:

- production acceptance `PASS`
- `production_accepted=true`
- blockers `[]`

- [ ] **Step 8: Preserve evidence**

Save additive output files only. Do not edit Voice 1.0 output files.

Expected output files:

- `outputs/sara-omega-voice-1-1-job-receipts.json`
- `outputs/sara-omega-voice-1-1-benchmark.json`
- `outputs/sara-omega-voice-1-1-restart-persistence.json`
- `outputs/sara-omega-voice-1-1-acceptance-summary.json`

- [ ] **Step 9: Final verification**

Run:

```bash
pytest -q
git status --short --branch
```

Expected:

- tests pass
- repo clean except intentional output artifacts if they are not committed
