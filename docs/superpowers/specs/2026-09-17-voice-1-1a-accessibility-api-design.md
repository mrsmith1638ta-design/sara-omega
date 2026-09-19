# SARA OMEGA Voice 1.1A Accessibility API Design

## Purpose

Voice 1.1A exposes a limited user-facing accessibility voice API without changing the certified Voice 1.1 baseline. It adds a separately authorized trust surface around the accepted voice engine: OAuth scope, durable entitlement, tenant isolation, bounded rate limits, privacy controls, abuse controls, accessibility preferences, and independent production acceptance evidence.

Voice 1.1A consumes Voice 1.1 as an internal dependency. It does not redefine or recertify the Piper renderer, Cori model, pronunciation dictionary, speech-rate mappings, audio receipt digest rules, or owner-only Voice 1.1 routes.

## Immutable Baselines

Voice 1.0 remains the immutable production provenance baseline:

- Source commit: `30c1f606092b6d4043413a185d8e0ac8d3458de2`
- Production deployment: `08bba7e1-9b51-4656-a8a2-6e4b3cf32575`
- Voice profile: `sara_elegant_british_v1`
- Piper model: `en_GB-cori-high`
- Pinned model SHA-256: `470b4dd634c98f8a4850d7626ffc3dfc90774628eeef6605a6dd8f88f30a5903`

Voice 1.1 remains the immutable internal certification baseline:

- Final implementation commit: `3b8948894cf7a93472a7289079ae41ba99c2a096`
- SARA deployment: `ffa3e879-a610-4d57-885b-e76de546fcf5`
- Piper deployment: `0a831729-4f80-4981-ae17-a888108ef82e`
- Owner-only routes: `/v1/voice/jobs`, `/v1/voice/jobs/{job_id}`, `/v1/voice/jobs/{job_id}/stop`, and `/v1/voice/jobs/{job_id}/receipts`

Voice 1.1A must not edit, replace, or append to any accepted Voice 1.0 or Voice 1.1 evidence artifact. It produces a new evidence family and ROAD acceptance record.

## Release Boundary

Voice 1.1A is a limited authenticated accessibility release, not a general public text-to-speech service.

Activation requires both:

- `SARA_VOICE_1_1A_ENABLED=true`
- `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=true`

If either flag is false, every Voice 1.1A route returns `404`. This preserves the certified Voice 1.1 external behavior under its accepted configuration.

Activation additionally requires:

- Voice 1.1 remains enabled and production-accepted.
- OAuth identity persistence is available.
- The access token contains `sara.voice.accessibility`.
- The principal has an active, unexpired Voice 1.1A entitlement.
- The entitlement resolves to an active tenant membership stored by SARA.
- Voice 1.1A durable state and fail-safe checkpoints are available.
- Per-user and per-tenant limits permit the operation.

Any missing dependency fails closed. No request field can override these checks.

## Non-Negotiable Constraints

- Do not change the owner-only authorization or response contract of Voice 1.1 routes.
- Do not expose owner routes through OAuth.
- Do not grant accessibility authority to `GPT_ACTION_TOKEN` or `TEST_TOKEN`.
- Do not accept a tenant ID, user ID, model ID, voice ID, model path, service URL, Piper argument, pronunciation rule, or arbitrary synthesis control from a user request.
- Do not import Piper into the SARA application process.
- Do not weaken the pinned model SHA-256 gate.
- Do not store OAuth tokens, Piper tokens, raw private service URLs, or hidden prompts.
- Do not persist raw transcripts by default.
- Do not use IP address, session ID, display name, or caller-supplied metadata as identity or tenancy.
- Do not permit cross-tenant job, preference, transcript, audio, or receipt access, including through identifier enumeration.
- Do not create a new cloud service, database service, volume, or domain. Durable state uses the existing `SARA_DATA_DIR` volume.
- Do not activate production exposure until the exact deployed commit passes the separate Voice 1.1A acceptance gate.

## Recommended Architecture

### OAuth Identity

The existing `UserIdentityStore` remains the source of authenticated `OAuthPrincipal` values. Voice 1.1A requires the additional OAuth scope `sara.voice.accessibility`.

OAuth scope is necessary but not sufficient. Scope proves that the registered client and user authorized the capability; it does not prove current product entitlement, tenant status, or release policy.

### Accessibility Access Store

Add `app/voice_accessibility.py` with a `VoiceAccessibilityStore` backed by `SARA_DATA_DIR/sara_voice_accessibility.db`. It uses SQLite WAL, `busy_timeout=10000`, `synchronous=FULL`, strict transactions, and keys derived through `derive_secret_key` with Voice 1.1A-specific domain separation.

The store owns:

- tenant records;
- user-to-tenant membership;
- accessibility voice entitlements;
- accessibility preferences;
- durable per-user and per-tenant usage windows;
- bounded concurrency leases;
- privacy consent and retention state;
- encrypted transcript records when explicitly enabled;
- job ownership metadata and receipt references;
- revocation and administrative audit events.

The store does not duplicate OAuth credentials and does not store raw access tokens.

### Accessibility Gateway

Add `app/voice_accessibility_http.py` as an `APIRouter`. It performs, in order:

1. Voice 1.1A dual-release-gate check.
2. Bearer token extraction and OAuth principal resolution.
3. `sara.voice.accessibility` scope check.
4. Active account, tenant membership, and entitlement resolution.
5. Fail-safe readiness and pre-dispatch checkpoint.
6. Per-user, per-tenant, and concurrency-limit reservation.
7. Request validation and privacy-policy resolution.
8. Invocation of the existing Voice 1.1 orchestration interfaces.
9. Tenant-bound job metadata and receipt recording.
10. Lease release and usage finalization in a `finally` path.

The gateway never trusts tenancy or entitlement data from the HTTP body.

### Voice 1.1 Adapter

Voice 1.1A may call `VoiceJobManager` through a narrow adapter that adds an opaque ownership context outside the certified receipt schema. Existing `VoiceJob`, `AudioReceipt`, control presets, model identity, and pronunciation behavior remain unchanged.

Public job IDs must be random and unguessable. Authorization is still checked on every access; unguessability is defense in depth, not an access-control mechanism.

## Durable Data Model

### `voice_tenants`

- `tenant_id TEXT PRIMARY KEY` - server-generated UUID
- `status TEXT NOT NULL` - `ACTIVE` or `SUSPENDED`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### `voice_memberships`

- `user_uuid TEXT PRIMARY KEY`
- `tenant_id TEXT NOT NULL`
- `status TEXT NOT NULL` - `ACTIVE` or `SUSPENDED`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

One user belongs to exactly one Voice 1.1A tenant in this release. Multi-tenant switching is out of scope.

### `voice_entitlements`

- `user_uuid TEXT PRIMARY KEY`
- `tenant_id TEXT NOT NULL`
- `status TEXT NOT NULL` - `ACTIVE`, `SUSPENDED`, or `REVOKED`
- `not_before TEXT NOT NULL`
- `expires_at TEXT`
- `granted_by_hash TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Entitlement resolution verifies that membership and entitlement name the same tenant. Revocation takes effect on the next request and blocks job status, audio, stop, receipt, and preference routes as well as new synthesis.

### `voice_preferences`

- `user_uuid TEXT PRIMARY KEY`
- `tenant_id TEXT NOT NULL`
- `speech_rate TEXT NOT NULL`
- `preserve_transcript INTEGER NOT NULL`
- `transcript_retention_seconds INTEGER NOT NULL`
- `updated_at TEXT NOT NULL`

Preferences are limited to `slower`, `normal`, and `faster`. Voice selection, raw Piper controls, and user-managed pronunciation rules are out of scope.

### `voice_jobs`

- `job_id TEXT PRIMARY KEY`
- `user_uuid_hash TEXT NOT NULL`
- `tenant_id_hash TEXT NOT NULL`
- `source_response_sha256 TEXT NOT NULL`
- `status TEXT NOT NULL`
- `preserve_transcript INTEGER NOT NULL`
- `transcript_expires_at TEXT`
- `created_at TEXT NOT NULL`
- `completed_at TEXT`
- `stopped_at TEXT`

The database stores keyed hashes of user and tenant identifiers in job records. Ownership lookup hashes the authenticated principal's resolved identifiers and compares both values.

### `voice_transcripts`

- `job_id TEXT PRIMARY KEY`
- `ciphertext BLOB NOT NULL`
- `expires_at TEXT NOT NULL`
- `created_at TEXT NOT NULL`

Transcript ciphertext uses authenticated encryption with a Voice 1.1A-specific key. Expired transcript rows are deleted during bounded maintenance and are never returned after expiry, even if deletion has not yet run.

### `voice_usage_windows`

- `subject_hash TEXT NOT NULL`
- `subject_kind TEXT NOT NULL` - `USER` or `TENANT`
- `window_kind TEXT NOT NULL` - `MINUTE` or `DAY`
- `window_started_at TEXT NOT NULL`
- `job_count INTEGER NOT NULL`
- `character_count INTEGER NOT NULL`
- primary key over subject, kind, and window

### `voice_leases`

- `lease_id TEXT PRIMARY KEY`
- `user_uuid_hash TEXT NOT NULL`
- `tenant_id_hash TEXT NOT NULL`
- `expires_at TEXT NOT NULL`
- `created_at TEXT NOT NULL`

Expired leases do not count toward concurrency and are pruned transactionally.

### `voice_access_audit`

- `event_id TEXT PRIMARY KEY`
- `event_type TEXT NOT NULL`
- `actor_hash TEXT NOT NULL`
- `tenant_id_hash TEXT`
- `target_user_hash TEXT`
- `reason_code TEXT NOT NULL`
- `created_at TEXT NOT NULL`

Audit rows contain bounded reason codes and hashes, never tokens or raw transcripts.

## Entitlement Administration

Voice 1.1A entitlement changes are owner-only control-plane operations:

- `POST /admin/voice-accessibility/entitlements`
- `POST /admin/voice-accessibility/entitlements/{public_user_id}/revoke`
- `GET /admin/voice-accessibility/entitlements/{public_user_id}`
- `DELETE /admin/voice-accessibility/data/{public_user_id}`

Granting an entitlement creates or selects a server-owned tenant, creates the membership, and records an expiry when supplied. The first release supports owner-managed individual tenants by default: one tenant per entitled user. Shared organizational tenants require a later explicit design because they expand privacy and delegation semantics.

Grant and revoke operations require `OWNER_TOKEN`, fail-safe pre-mutation checkpoints, and durable audit rows. OAuth, action, and test credentials cannot administer entitlements in production.

The delete operation removes that user's Voice 1.1A preferences and retained transcripts after a fail-safe checkpoint. It does not delete OAuth identity, entitlement history, receipt digests, bounded usage records, or unrelated SARA memory. Its response contains counts only.

## User API Contract

All user routes require the dual release gate, OAuth, `sara.voice.accessibility`, active tenant membership, and active entitlement.

### `POST /v1/accessibility/voice/jobs`

Request:

```json
{
  "text": "SARA can read this response aloud.",
  "speech_rate": "normal",
  "preserve_transcript": false
}
```

`speech_rate` may be omitted to use the authenticated user's stored preference. A request may use only an approved preset. `preserve_transcript` defaults to the stored preference, which defaults to false.

All Voice 1.1A request models use strict schema validation with unknown fields forbidden. Caller-supplied identity, tenant, model, service, and synthesis-control fields therefore fail with `422` rather than being silently accepted.

The response contains job state, segment metadata, source digest, and receipt IDs. It does not contain raw transcript text, tenant ID, internal user UUID, private service URL, or service token.

### `GET /v1/accessibility/voice/jobs/{job_id}`

Returns non-secret job and segment state only after job ownership matches both the authenticated user and resolved tenant. Missing and unauthorized jobs both return `404` to reduce identifier probing.

### `POST /v1/accessibility/voice/jobs/{job_id}/stop`

Requests idempotent stop after the same ownership check. Revoked users cannot stop or inspect old jobs through the public API; owner incident controls remain separate.

### `GET /v1/accessibility/voice/jobs/{job_id}/segments/{segment_id}/audio`

Returns `audio/wav` for a completed segment after entitlement and ownership checks. It sets `Cache-Control: private, no-store` and does not expose a durable public URL. Audio is retained only for the bounded in-process job window in Voice 1.1A; after expiry or restart it returns `404` and can be regenerated from an authorized source response when policy permits.

### `GET /v1/accessibility/voice/jobs/{job_id}/receipts`

Returns the accepted Voice 1.1 receipt fields plus a Voice 1.1A access-envelope digest binding the receipt to hashed tenant and user ownership. It never returns the raw ownership identifiers.

### `GET /v1/accessibility/voice/jobs/{job_id}/transcript`

Returns the preserved transcript only when the authenticated user owns the job, transcript preservation was explicitly enabled, and the retention deadline has not passed. It sets `Cache-Control: private, no-store`. Disabled, absent, expired, and unauthorized transcripts return `404` without revealing which condition applied.

### `GET /v1/accessibility/voice/preferences`

Returns the user's bounded speech-rate and transcript-preservation preferences.

### `PUT /v1/accessibility/voice/preferences`

Accepts only:

```json
{
  "speech_rate": "normal",
  "preserve_transcript": false,
  "transcript_retention_seconds": 0
}
```

Allowed retention is `0` when preservation is false, or one of `900`, `3600`, and `86400` seconds when preservation is true. Preferences are private to the authenticated user.

## Rate Limits And Abuse Controls

Initial defaults are configuration-backed, positive integers with startup validation:

- Per user: 6 jobs per minute.
- Per user: 100 jobs per day.
- Per user: 100,000 characters per day.
- Per tenant: 20 jobs per minute.
- Per tenant: 500 jobs per day.
- Per tenant: 500,000 characters per day.
- Concurrent jobs: 1 per user and 4 per tenant.
- Maximum text: 4,000 characters, additionally bounded by the existing Voice 1.1 segmenter.

Limits are reserved atomically before synthesis. A rejected request does not consume a job quota, while an accepted synthesis attempt consumes quota even if Piper later fails. This prevents deliberate renderer-failure loops from bypassing abuse controls.

Responses use `429` with a bounded reason code and `Retry-After` where calculable. They do not reveal another user's or tenant's utilization.

Repeated malformed, unauthorized, entitlement-rejected, or ownership-mismatch requests are recorded as bounded audit events. Voice 1.1A does not automatically disable OAuth accounts; incident escalation and entitlement suspension remain owner actions.

## Privacy And Retention

- Transcript preservation is false by default.
- With preservation disabled, only source and segment digests, counts, status, and receipt metadata persist.
- With preservation enabled, transcript content is encrypted at rest and expires after the selected bounded retention period.
- Raw audio is not durably persisted by Voice 1.1A.
- API responses set `Cache-Control: private, no-store` where transcript, preference, or audio state is involved.
- Logs contain request IDs, bounded reason codes, counts, and keyed subject hashes only.
- Public responses contain `public_user_id` only where identity confirmation is necessary; Voice 1.1A job routes omit it.
- Preference deletion or entitlement revocation does not silently extend transcript retention.
- An owner-only purge operation may delete one user's Voice 1.1A transcripts and preferences without deleting OAuth identity or unrelated memory.

## Error Contract

- `401`: missing, malformed, expired, or revoked OAuth access token.
- `403`: valid OAuth principal lacks required scope or active entitlement.
- `404`: release gated, job absent, segment absent, or ownership mismatch.
- `409`: concurrency lease unavailable or conflicting preference update.
- `422`: invalid text, rate preset, transcript policy, or request shape.
- `429`: user or tenant quota exceeded.
- `502`: accepted synthesis failed in the isolated voice service.
- `503`: identity, accessibility store, fail-safe, Voice 1.1, or Piper dependency unavailable.

Errors use bounded public reason codes. Internal exception text, SQL details, tokens, tenancy, and private URLs are never returned.

## Threat Model

### Cross-Tenant Object Access

An attacker submits another job or segment ID. Every object lookup includes keyed user and tenant ownership derived from the authenticated principal. Unauthorized and missing objects are indistinguishable `404` responses.

### Tenant Forgery

An attacker submits a tenant identifier in a body, query, header, or session ID. Strict API schemas reject unrecognized fields, and tenancy is resolved only from SARA's durable membership and entitlement records.

### Scope Or Credential Confusion

An action token, test token, owner token on a user route, or OAuth token without the voice scope attempts access. User routes accept only OAuth principals with the required scope; owner administration remains on separate routes.

### Revoked Entitlement Reuse

A previously authorized user reuses an unexpired OAuth token after Voice 1.1A revocation. Entitlement is checked on every request, so revocation does not wait for OAuth expiry.

### Quota Evasion

An attacker varies session IDs, IP addresses, job IDs, or request metadata. Quotas use keyed internal user and tenant identities and persist across process restarts.

### Concurrency Exhaustion

An attacker starts jobs that fail or disconnect. Durable leases have short expiries and are released in `finally`; expired leases are pruned before admission.

### Transcript Leakage

An attacker enumerates job IDs, inspects logs, reads database bytes, or requests expired content. Ownership checks, authenticated encryption, redacted logging, and expiry checks prevent plaintext disclosure.

### Receipt Enumeration

An attacker requests receipts for another user. Receipt access follows the job ownership check, and the access envelope contains only keyed hashes.

### Parameter Injection

An attacker supplies arbitrary model names, rates, Piper flags, paths, URLs, or pronunciation rules. Strict schemas accept only text, approved rate presets, and bounded privacy choices.

### Evidence Contamination

An operator accidentally overwrites Voice 1.0 or Voice 1.1 evidence. Voice 1.1A tools write only `sara-omega-voice-1-1a-*` artifacts and verify immutable baseline file digests before acceptance.

## Test Strategy

### Unit Tests

- OAuth voice scope is required.
- Membership and entitlement must be active, aligned to the same tenant, current, and unexpired.
- Entitlement revocation takes effect immediately.
- Preferences accept only approved rates and retention choices.
- Transcript preservation defaults to false.
- Transcript ciphertext does not contain plaintext and is unavailable after expiry.
- User and tenant usage windows survive store restart.
- Atomic reservations prevent quota and concurrency races.
- Expired leases are ignored and pruned.
- Audit records contain no raw token, transcript, user UUID, or tenant UUID.

### API And Adversarial Tests

- Both release flags are required.
- Existing Voice 1.1 owner routes retain their accepted behavior.
- OAuth, action, test, and owner credential classes cannot be confused.
- Missing scope and inactive entitlement fail closed.
- Forged tenant fields cannot alter tenancy.
- Two users in different tenants cannot inspect, stop, hear, or retrieve receipts for each other's jobs.
- Reusing the same job ID path under another tenant returns `404`.
- Per-user and per-tenant minute, day, character, and concurrency limits are enforced.
- Restart cannot reset durable quotas or entitlement revocation.
- Audio responses are `audio/wav` with private no-store headers.
- Invalid rate, retention, text size, and unexpected fields are rejected.
- Piper failures do not leak details and still finalize usage and leases safely.
- Transcript and secret scans cover logs, SQLite bytes, JSON evidence, and HTTP responses.

### Regression Tests

- Voice 1.0 synthesis compatibility remains green.
- Voice 1.1 owner/internal jobs, stop, receipts, controls, and persistence tests remain green.
- OAuth enrollment, token rotation, revocation, and user-memory isolation remain green.
- The full repository test suite passes on the exact release tree.

## Acceptance And Evidence

Voice 1.1A creates new evidence under `outputs/` with the prefix `sara-omega-voice-1-1a-`. Required artifacts are:

- design and implementation-plan commit SHAs;
- final implementation commit SHA;
- SARA deployment ID and Piper deployment ID;
- immutable Voice 1.0 and Voice 1.1 baseline artifact digests;
- entitlement grant and revocation test evidence using redacted identifiers;
- cross-tenant adversarial probe results;
- user and tenant rate-limit probe results;
- privacy and transcript-retention probe results;
- one live entitled-user spoken-response transaction with source, segment, receipt, and audio digests;
- restart proof showing entitlement, quota, privacy, and revocation persistence;
- secret and plaintext scan result;
- ROAD/SISO/Madhouse review identifiers where available;
- separate Voice 1.1A ROAD production acceptance result.

The live acceptance transaction must use a dedicated certification account and tenant. Evidence records hashes or bounded public identifiers, never OAuth tokens, internal UUIDs, transcripts, or private service URLs.

Production activation order:

1. Deploy the exact tested Voice 1.1A commit with both exposure flags false.
2. Verify Voice 1.0 and Voice 1.1 regressions and immutable evidence digests.
3. Configure the OAuth client to allow `sara.voice.accessibility`.
4. Create the certification tenant and entitlement through the owner control plane.
5. Enable `SARA_VOICE_1_1A_ENABLED` while the public exposure flag remains false and run internal probes.
6. Obtain ROAD/SISO/Madhouse acceptance for the exact deployment.
7. Enable `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED`.
8. Perform one real entitled-user spoken-response transaction.
9. Capture final evidence and re-run ROAD production acceptance.

Any failed checkpoint stops activation. Rollback disables either Voice 1.1A flag; Voice 1.1 owner functionality remains available and unchanged.

## Out Of Scope

- anonymous voice access;
- shared API-key accessibility access;
- public signup or self-service entitlement purchase;
- shared organizational tenants or tenant administrators;
- arbitrary voice or model selection;
- user-uploaded pronunciation dictionaries;
- voice cloning or speaker enrollment;
- durable raw audio storage or public audio URLs;
- speech recognition, wake words, phone integration, or real-time bidirectional streaming;
- modifying the Voice 1.0 or Voice 1.1 certification capsule.

## Acceptance Criteria

Voice 1.1A is accepted only when all of the following are true:

1. Voice 1.0 and Voice 1.1 evidence artifacts match their pre-release digests.
2. Voice 1.1 owner routes preserve their accepted behavior.
3. Both Voice 1.1A activation flags fail closed independently.
4. Only an OAuth principal with `sara.voice.accessibility` and an active entitlement can use the API.
5. Tenant identity is resolved server-side and cannot be forged by request data.
6. Cross-user and cross-tenant job, audio, receipt, preference, and transcript access is denied.
7. User and tenant quotas and concurrency limits are durable and race-safe.
8. Transcript preservation is opt-in, encrypted, bounded, and expiry-enforced.
9. Audio delivery uses authenticated no-store responses and no durable public URL.
10. Entitlement revocation blocks every user route immediately.
11. Accessibility controls remain limited to certified Voice 1.1 presets and behavior.
12. Adversarial, privacy, abuse, restart, regression, and full repository tests pass.
13. One live entitled-user spoken-response transaction succeeds and is receipt-bound.
14. Voice 1.1A evidence contains no secrets, raw internal IDs, private URLs, or transcript plaintext.
15. The separate Voice 1.1A ROAD production acceptance result is PASS for the exact deployed commit.
