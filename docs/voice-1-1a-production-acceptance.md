# Voice 1.1A Production Acceptance

Voice 1.1A exposes a limited OAuth-authenticated accessibility API around the certified Voice 1.1 engine. This runbook creates a separate acceptance chain. Do not modify, append to, rename, or replace any Voice 1.0 or Voice 1.1 capsule or evidence artifact.

## Required Boundary

- Voice 1.0 commit: `30c1f606092b6d4043413a185d8e0ac8d3458de2`
- Voice 1.0 deployment: `08bba7e1-9b51-4656-a8a2-6e4b3cf32575`
- Voice 1.1 commit: `3b8948894cf7a93472a7289079ae41ba99c2a096`
- Voice 1.1 SARA deployment: `ffa3e879-a610-4d57-885b-e76de546fcf5`
- Voice 1.1 Piper deployment: `0a831729-4f80-4981-ae17-a888108ef82e`
- Voice 1.1A evidence prefix: `sara-omega-voice-1-1a-`

Voice 1.1A must use the existing Railway project, SARA service, Piper service, data volume, and domain. It must not create another cloud resource.

## Local Certification

Run from the exact candidate tree:

```powershell
pytest -q
python -m compileall -q main.py app sara_unified voice_service tools
git diff --check
git status --short --branch
```

All commands must exit zero. Record `git rev-parse HEAD`; that exact commit is the only deployable candidate.

Before deployment, hash the accepted Voice 1.0 and Voice 1.1 output artifacts. Store those hashes in `outputs/sara-omega-voice-1-1a-immutable-baselines.json`. Later acceptance must reproduce every hash exactly.

## Stage With Exposure Closed

Deploy the exact tested commit to the existing SARA service with:

```text
SARA_SOURCE_COMMIT_SHA=<exact-candidate-commit>
SARA_VOICE_1_1A_ENABLED=false
SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=false
```

Verify readiness, production acceptance, owner Voice 1.1 synthesis, and Piper model integrity. Do not redeploy Piper unless its accepted deployment is unhealthy or the implementation changed the renderer contract.

## OAuth And Entitlement

Add `sara.voice.accessibility` to the existing registered OAuth client's allowed scope. Enroll a dedicated certification user through the existing invitation flow and complete a real authorization-code exchange. Never write the access token, refresh token, authorization code, password, client credential, owner credential, or internal UUID to evidence.

Use the owner control plane to create the certification user's individual Voice 1.1A tenant and entitlement. Capture only bounded public identity or keyed hashes in `outputs/sara-omega-voice-1-1a-entitlement.json`.

## Internal Gate

Set:

```text
SARA_VOICE_1_1A_ENABLED=true
SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=false
```

Every user-facing Voice 1.1A route must still return `404`. Owner Voice 1.1 must remain functional. Run ROAD blocking-dependency, SISO, and Madhouse review against the exact candidate deployment before opening the public gate.

## Adversarial Acceptance

Using two dedicated certification users in separate individual tenants, prove:

- missing scope and revoked entitlement fail closed;
- forged tenant, user, model, service, pronunciation, and raw-control fields receive `422`;
- neither user can inspect, stop, hear, retrieve receipts for, or retrieve transcripts from the other's jobs;
- missing and non-owned object identifiers both return `404`;
- user and tenant minute, day, character, and concurrency limits cannot be bypassed with IP, session, header, or identifier changes;
- renderer failure consumes accepted quota, releases its lease, and returns no private exception text;
- transcript preservation defaults off, opted-in plaintext is encrypted at rest, and expired transcript access returns `404`;
- restart preserves entitlement, revocation, preferences, and consumed quota;
- valid audio uses `audio/wav` and `Cache-Control: private, no-store`;
- receipt access envelopes contain no raw user or tenant identifiers.

Save redacted results as:

- `outputs/sara-omega-voice-1-1a-isolation.json`
- `outputs/sara-omega-voice-1-1a-limits.json`
- `outputs/sara-omega-voice-1-1a-privacy.json`
- `outputs/sara-omega-voice-1-1a-restart.json`

## Public Activation And Live Audio

After ROAD/SISO/Madhouse pre-exposure approval, set `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=true`. Submit a two-sentence request with the certification OAuth account, retrieve receipts, fetch one authenticated segment, and verify the WAV SHA-256 equals its receipt. Confirm the second certification tenant receives `404` for the same job and segment identifiers.

Save only the user-facing WAV and redacted transaction metadata:

- `outputs/sara-omega-voice-1-1a-spoken-response.wav`
- `outputs/sara-omega-voice-1-1a-transaction.json`

Build `outputs/sara-omega-voice-1-1a-acceptance-summary.json` with `tools/voice_1_1a_acceptance_probe.py`. It must bind the exact source commit, SARA deployment, accepted Piper deployment, immutable baseline hashes, transaction digests, entitlement test, isolation test, limits test, privacy test, restart test, and ROAD result.

Scan every new output for credentials, private URLs, raw internal identifiers, and transcript plaintext. Re-hash all older artifacts and require exact matches. Final ROAD production acceptance must report `PASS` for the exact deployment.

## Rollback

Set either `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=false` or `SARA_VOICE_1_1A_ENABLED=false`. Verify every Voice 1.1A user route returns `404`, owner Voice 1.1 still speaks, and no older evidence changed. Entitlements and quotas remain durable for investigation; rollback does not silently delete or extend transcript retention.
