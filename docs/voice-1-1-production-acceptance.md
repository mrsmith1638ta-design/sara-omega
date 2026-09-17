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
