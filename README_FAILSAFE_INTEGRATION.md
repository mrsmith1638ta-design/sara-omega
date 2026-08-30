# SARA OMEGA — SIOS V3.2 fail-safe hardening integration

This repository retains its base application version (`2.5.2`) and adds the hardening profile `SIOS-V3.2-FAILSAFE-1`.

## Runtime activation

Set a dedicated backup encryption key through one of:

- `SARA_FAILSAFE_MASTER_KEY_HEX` — at least 32 random bytes encoded as hex.
- `SARA_FAILSAFE_MASTER_KEY_B64` — at least 32 random bytes encoded as Base64.

Recommended production settings:

- `SARA_FAILSAFE_REQUIRED=true`
- `SARA_FAILSAFE_ROOT=/data/sara-failsafe` where `/data` is a persistent Railway Volume or other durable mounted storage.

Do not reuse `OWNER_TOKEN`, `TEST_TOKEN`, `OPENAI_API_KEY`, or a SIOS bearer token as the backup key.

## Installed controls

- AES-256-GCM encrypted atomic snapshots.
- HKDF-SHA3-512 key derivation.
- SHA3-512 state integrity and HMAC-SHA3-512 envelope authentication.
- Snapshot chain continuity.
- Secret-key redaction before snapshot encryption.
- Pre-mutation checkpoints for session and rate-limit state.
- Unhandled-exception and shutdown checkpoints.
- Owner-only manual checkpoint and verified restore endpoints.
- Epistemic authority classes and SIOS relay implementation installed under `sara_v32_hardening.py`.
- SIOS relay remains inactive until a real SIOS authority endpoint/token provider is configured and wired to a governed dispatch path.

## Endpoints

- `GET /admin/failsafe/status`
- `POST /admin/failsafe/checkpoint`
- `POST /admin/failsafe/restore-latest`

All three require the existing owner bearer token.
