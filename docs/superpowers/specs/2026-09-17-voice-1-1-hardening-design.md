# SARA OMEGA Voice 1.1 Hardening Design

## Purpose

SARA Voice 1.1 hardens the production-active governed Piper voice system without modifying the accepted Voice 1.0 evidence. Voice 1.1 certifies the internal voice engine and governance layer first: sentence-by-sentence speech, interrupt/stop support, pronunciation handling, bounded speech-rate controls, latency/load evidence, audio audit receipts tied to source-response digests, transcript preservation, and restart/persistence proof.

Voice 1.0 remains the immutable baseline:

- Source commit: `30c1f606092b6d4043413a185d8e0ac8d3458de2`
- Production deployment: `08bba7e1-9b51-4656-a8a2-6e4b3cf32575`
- Production-active ROAD capsule: `outputs/sara-omega-voice-production-active-road-capsule.md`
- Voice profile: `sara_elegant_british_v1`
- Piper model: `en_GB-cori-high`
- Pinned model SHA-256: `470b4dd634c98f8a4850d7626ffc3dfc90774628eeef6605a6dd8f88f30a5903`

Voice 1.1 evidence must reference that capsule but must not edit or replace it.

## Certification Boundary

The first Voice 1.1 certification is owner/internal only.

Public accessibility exposure is not part of Voice 1.1. Voice 1.1 designs the accessibility API contract and proves the underlying capabilities, but public accessibility routes remain disabled behind an explicit release gate until Voice 1.1A.

Release sequence:

1. Voice 1.1: internal/owner certified baseline.
2. Voice 1.1A: limited user-facing accessibility API after Voice 1.1 passes ROAD/SISO/Madhouse and after separate rate limits, tenant isolation, privacy rules, entitlement checks, and accessibility-specific acceptance tests exist.

Certification validates the voice engine and governance layer first. Public accessibility exposure is a separately authorized surface, not part of the initial trust boundary.

## Non-Negotiable Constraints

- Do not import `piper-tts` into the main SARA runtime.
- Keep Piper isolated in `voice_service/`.
- Keep the Cori model filename and SHA-256 integrity gate mandatory.
- Do not allow callers to choose arbitrary model IDs, model paths, executable arguments, service URLs, filesystem paths, or raw Piper parameters.
- Do not persist raw synthesized text in receipts or audit events unless transcript preservation is explicitly requested under the internal certification contract.
- Transcript preservation must be explicit, bounded, and tied to a source-response digest.
- Do not expose public accessibility routes in Voice 1.1.
- Do not weaken existing owner/action/test token separation.
- Do not expand `GPT_ACTION_TOKEN` into voice control authority for Voice 1.1.
- Preserve the existing one-shot `/v1/voice/synthesize` behavior for compatibility.
- All new production acceptance evidence must be new evidence, not an edit to Voice 1.0 acceptance artifacts.

## Architecture

Voice 1.1 adds an internal orchestration layer in SARA core while preserving the isolated Piper renderer.

Components:

1. `sara_unified.voice.segmenting`
   - Deterministically splits approved response text into bounded sentence segments.
   - Produces stable segment IDs and segment digests.

2. `sara_unified.voice.pronunciation`
   - Applies a SARA-owned pronunciation dictionary before synthesis.
   - Tracks dictionary version and dictionary digest in receipts.
   - Does not accept arbitrary caller-supplied replacement rules in Voice 1.1.

3. `sara_unified.voice.controls`
   - Defines bounded speech-rate presets and maps them to safe SARA-owned synthesis values.
   - Rejects arbitrary caller-provided Piper parameters.

4. `sara_unified.voice.jobs`
   - Owns voice job lifecycle, stop state, transcript preservation flags, receipt assembly, and timing data.
   - Provides in-memory job storage for first implementation, with a small bounded retention window.
   - Can later move to durable storage without changing the API contract.

5. `sara_unified.voice.receipts`
   - Creates audio receipt records for each segment and for the whole job.
   - Binds source-response digest, segment digest, audio digest, profile ID, model ID, dictionary digest, control digest, timing, and deployment metadata.

6. Production `main.py` bridge
   - Exposes owner-only Voice 1.1 internal routes on the current production entrypoint.
   - Reuses `sara_unified` voice modules rather than duplicating logic.

7. `voice_service`
   - Remains a renderer only.
   - Adds optional health metadata needed for restart/persistence evidence, such as model SHA, model path, readiness, and whether bootstrap reused an existing verified model.

## Data Flow

### Owner/Internal Segmented Speech

1. Owner submits text to `POST /v1/voice/jobs`.
2. SARA validates owner authority and Voice 1.1 enablement.
3. SARA computes the source-response digest from the submitted text.
4. SARA splits the text into bounded sentence segments.
5. SARA applies the active pronunciation dictionary.
6. SARA applies a bounded speech-rate preset.
7. SARA synthesizes each segment through the existing Piper service client.
8. Before each segment request, SARA checks whether the job has been stopped.
9. SARA records per-segment timing, text digest, transformed-text digest, audio digest, and synthesis metadata.
10. SARA returns a job response containing status, segment metadata, receipt IDs, and either segment audio payloads or an archive/manifest path depending on implementation plan choice.

### Interrupt/Stop

1. Owner calls `POST /v1/voice/jobs/{job_id}/stop`.
2. SARA marks the job stop token as requested.
3. A currently executing Piper request is allowed to finish, because Voice 1.1 does not kill the renderer process mid-call.
4. SARA suppresses any later segment requests for that job.
5. SARA records stop timing and final job state.

Stop latency is measured from the stop request to the point where SARA stops submitting new segments.

### Restart/Persistence Probe

1. Voice service starts with `/models/en_GB-cori-high.onnx`.
2. Bootstrap verifies exact filename, matching `.onnx.json`, and pinned SHA-256.
3. If model/config are already present and valid, bootstrap reuses them.
4. Restart/persistence acceptance checks logs or service metadata proving the existing model was verified and reused.
5. Any missing, renamed, or digest-mismatched model fails closed.

## API Contract

### Owner/Internal Routes

These routes are enabled only when `SARA_VOICE_1_1_ENABLED=true`. They require owner authority in production.

#### `POST /v1/voice/jobs`

Request:

```json
{
  "text": "SARA OMEGA voice hardening is ready. This is the second sentence.",
  "speech_rate": "normal",
  "preserve_transcript": true,
  "return_audio": "segments"
}
```

Allowed `speech_rate` values:

- `slower`
- `normal`
- `faster`

Allowed `return_audio` values:

- `none`
- `segments`
- `wav_archive`

Voice 1.1 implementation may initially support only `none` and `segments`; unsupported declared values must fail clearly with `422`, not silently degrade.

Success:

```json
{
  "job_id": "voice-job-...",
  "status": "completed",
  "profile_id": "sara_elegant_british_v1",
  "model_id": "en_GB-cori-high",
  "source_response_sha256": "...",
  "segments": [
    {
      "segment_id": "seg-0001",
      "status": "completed",
      "text_sha256": "...",
      "audio_sha256": "...",
      "duration_ms": 1234
    }
  ],
  "receipt_id": "voice-receipt-..."
}
```

Failure:

- `401` unauthenticated
- `403` authenticated but not owner
- `422` invalid text, too many segments, unsupported return mode, unsupported rate
- `503` Voice 1.1 disabled or Piper unavailable
- `502` Piper returns invalid audio or a failed response

#### `GET /v1/voice/jobs/{job_id}`

Returns the current job status and non-secret metadata. If transcript preservation is disabled, raw text is never returned.

#### `POST /v1/voice/jobs/{job_id}/stop`

Marks the job for stop and returns stop receipt metadata. This endpoint is idempotent: repeated stop requests return the same stopped state.

#### `GET /v1/voice/jobs/{job_id}/receipts`

Returns job and segment receipt metadata. It must not return tokens, private service URLs with credentials, or raw Piper internals.

#### `POST /internal/voice/restart-persistence-check`

Owner/internal route for certification runs only. It returns current voice service health metadata and, where available, deployment/log evidence that the model was reused from the persistent `/models` mount and verified by SHA-256.

This endpoint must not restart production by itself unless a separate Railway-control authority and explicit operator step are present. The certification plan may perform the restart through Railway tooling and then call this endpoint to capture evidence.

### Accessibility Contract For Voice 1.1A

Voice 1.1 designs but does not expose public accessibility routes.

Routes reserved for Voice 1.1A:

- `POST /v1/accessibility/voice/jobs`
- `GET /v1/accessibility/voice/jobs/{job_id}`
- `POST /v1/accessibility/voice/jobs/{job_id}/stop`
- `GET /v1/accessibility/voice/preferences`
- `PUT /v1/accessibility/voice/preferences`

In Voice 1.1, these routes must either not exist or must return a release-gated `404` or `403` unless all of the following are true:

- `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=true`
- Voice 1.1A ROAD evidence exists
- user identity is authenticated
- tenant isolation is active
- rate limits are active
- privacy rules are active
- entitlement checks are active

Voice 1.1A is out of scope for the first certification.

## Speech-Rate Controls

Voice 1.1 exposes only presets.

Initial mapping:

- `slower`: `length_scale=1.16`, `noise_scale=0.55`, `noise_w_scale=0.70`, `volume=0.95`
- `normal`: `length_scale=1.08`, `noise_scale=0.55`, `noise_w_scale=0.70`, `volume=0.95`
- `faster`: `length_scale=1.00`, `noise_scale=0.55`, `noise_w_scale=0.70`, `volume=0.95`

The implementation may tune these values during tests, but the spec must remain preset-based. Callers must not provide arbitrary floats.

## Pronunciation Dictionary

The pronunciation dictionary is SARA-owned configuration.

Minimum contract:

- dictionary ID
- dictionary version
- dictionary SHA-256
- ordered replacement rules
- maximum input length after replacement

Dictionary replacements are applied after text validation and before segment synthesis. Receipts include dictionary ID/version/digest, not the full dictionary content.

Voice 1.1 does not allow callers to upload or modify pronunciation entries through the API.

## Transcript Preservation

Voice 1.1 supports explicit transcript preservation for owner/internal certification.

Rules:

- `preserve_transcript=false` by default.
- If false, receipts contain only digests and counts.
- If true, transcript storage is permitted only in the internal job record for certification and must be bounded by retention policy.
- Transcript preservation must be visible in the receipt metadata.
- Transcript storage must never include service tokens or hidden system prompts.

Public user transcript preservation belongs to Voice 1.1A and requires separate privacy acceptance.

## Audio Receipts

Every completed segment receives an audio receipt.

Receipt fields:

- `receipt_id`
- `job_id`
- `segment_id`
- `profile_id`
- `model_id`
- `source_response_sha256`
- `segment_text_sha256`
- `transformed_segment_text_sha256`
- `audio_sha256`
- `audio_bytes`
- `wav_channels`
- `wav_frame_rate`
- `wav_duration_seconds`
- `speech_rate`
- `speech_control_digest`
- `pronunciation_dictionary_id`
- `pronunciation_dictionary_version`
- `pronunciation_dictionary_sha256`
- `voice_service_url_hash`
- `source_commit_sha`
- `deployment_id`
- `created_at`

Receipts do not include raw tokens, full private URLs with credentials, arbitrary raw text, or file paths beyond approved non-secret model path metadata.

## Benchmarks

Voice 1.1 acceptance requires benchmark evidence for:

- first segment audio latency
- full job latency
- per-segment latency distribution
- stop request latency
- owner/internal concurrent job behavior
- failed Piper behavior
- service restart recovery

Benchmark output must include:

- source commit
- deployment ID
- benchmark timestamp
- number of jobs
- number of segments
- p50/p95/p99 where sample size supports it
- maximum observed latency
- failure count
- timeout count
- environment name

The initial benchmark target is characterization, not an aggressive SLA. The implementation plan must define conservative pass/fail thresholds from a measured current-production baseline before Voice 1.1 can be accepted.

## Restart/Persistence Acceptance

Voice 1.1 restart/persistence acceptance passes only when:

1. The voice service is restarted or redeployed.
2. Startup verifies the existing Cori model file from `/models`.
3. Startup logs or health metadata prove the pinned SHA-256 was checked.
4. The service does not redownload the model when the valid model and config already exist.
5. A post-restart synthesis succeeds.
6. A model filename or digest mismatch test fails closed in automated tests.

The implementation may add explicit bootstrap metadata so tests do not depend only on log parsing.

## Security And Privacy

- Owner authority is required for Voice 1.1 internal endpoints.
- GPT action authority is not sufficient.
- Test authority may be allowed only in local/unit tests, not production acceptance.
- Stop requests are control operations and require the same owner boundary as synthesis jobs.
- Accessibility public routes are release-gated and out of scope.
- Raw transcript preservation is opt-in and bounded.
- Receipts contain digests by default.
- Voice service token handling remains server-side only.
- Piper remains a renderer with no governance, memory, tool, or execution authority.

## Test Strategy

Unit tests:

- sentence segmentation is deterministic and bounded
- empty and oversized text are rejected
- speech-rate presets map to approved bounded controls
- arbitrary rate floats are rejected
- pronunciation dictionary applies ordered replacements
- dictionary digest changes when rules change
- audio receipts bind source digest, segment digest, audio digest, profile, model, dictionary, and controls
- transcript preservation defaults to false
- transcript is preserved only when explicitly requested
- stop is idempotent
- stopped jobs do not synthesize later segments
- public accessibility routes are gated off in Voice 1.1

Integration tests with fake Piper:

- owner can create a segmented job
- non-owner cannot create, inspect, or stop jobs
- segment audio is returned when requested
- receipts contain no secret values
- Piper error maps to scoped `502`
- disabled Voice 1.1 maps to `503`

Voice service tests:

- valid persistent model is reused
- missing model fails closed
- wrong model filename fails closed
- wrong model digest fails closed
- health metadata includes non-secret model integrity state

Production acceptance probes:

- live owner/internal job with at least two segments
- live stop probe with a long enough multi-segment fake or controlled test path
- live receipt retrieval
- live benchmark run
- Railway restart/redeploy followed by persistence proof and synthesis
- ROAD acceptance remains PASS

## Evidence Strategy

Voice 1.1 produces new evidence files under `outputs/` and new ROAD evidence records. It does not edit:

- `outputs/sara-omega-voice-production-active-road-capsule.md`
- `outputs/sara-omega-production-piper-voice-evidence.json`
- `outputs/sara-omega-production-piper-voice.wav`
- `outputs/sara-omega-production-voice-activation-summary.json`

Required Voice 1.1 evidence:

- spec and implementation plan commit SHAs
- final implementation commit SHA
- deployment ID
- model SHA verification evidence
- segmented job receipt JSON
- benchmark JSON
- restart/persistence JSON
- ROAD production acceptance result
- Madhouse/SISO/ROAD review identifiers where available

## Out Of Scope

- public user-facing accessibility API activation
- tenant-level accessibility preferences
- user entitlements
- voice cloning
- arbitrary voice selection
- speaker enrollment
- speech recognition
- wake-word detection
- phone integration
- real-time low-latency streaming protocol guarantees
- killing an in-flight Piper process mid-synthesis

## Voice 1.1 Acceptance Criteria

Voice 1.1 is accepted only when all of the following are true:

1. Voice 1.0 capsule remains unchanged.
2. Repository tests pass.
3. Owner-only Voice 1.1 routes are deployed.
4. Public accessibility routes remain gated off.
5. A live owner/internal segmented speech job succeeds.
6. Interrupt/stop prevents later segment synthesis and records a stop receipt.
7. Pronunciation dictionary behavior is tested and receipt-bound.
8. Speech-rate controls are preset-only and bounded.
9. Audio receipts bind source-response digest to segment audio digests.
10. Transcript preservation is explicit and bounded.
11. Latency/load benchmark evidence is saved.
12. Restart/persistence evidence proves valid model reuse without weakening model integrity.
13. ROAD production acceptance remains PASS.
14. No secret values are stored in evidence.
