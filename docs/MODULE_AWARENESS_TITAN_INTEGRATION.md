# Module Awareness and TITAN Integration

This SARA Omega build integrates the supplied module-awareness and SARA-TITAN builds as
internal architecture modules.

The original ZIP contents were treated as source material, not executable deployment
instructions. Cloud Run deployment scripts, Firestore startup registration and hard-coded
GCP assumptions were not copied into the runtime path.

## Module Awareness Integration

Integrated from `sara-module-awareness-build`:

- module count and awareness snapshots
- baseline diffing
- NQHN route alias normalization
- QCR temporal context injection
- Daystar probe state and drift detection
- NSCS narrative continuity and memory consolidation
- SGE-style module compliance audit and advisory remediation patches

The integrated API surface is:

- `GET /module-awareness/health`
- `POST /module-awareness/registry/load`
- `POST /module-awareness/register`
- `GET /module-awareness/count`
- `GET /module-awareness/awareness`
- `POST /module-awareness/baseline`
- `GET /module-awareness/diff`
- `GET /nqhn/routes`
- `POST /nqhn/routes/register`
- `POST /nqhn/harmonize`
- `GET /qcr/temporal`
- `POST /daystar/probe/{service}`
- `GET /daystar/state`
- `GET /daystar/drift`
- `POST /nscs/narrative/append`
- `GET /nscs/narrative/{session_id}`
- `POST /nscs/consolidate`
- `GET /nscs/continuity/{session_id}`
- `GET /sge/audit`
- `GET /sge/audit/{service_id}`
- `POST /sge/remediate/{service_id}`

## TITAN Integration

Integrated from `sara-titan-build`:

- HMAC-SHA3-512 signed VOICE events
- strict VOICE event set: `VALIDATE`, `ORCHESTRATE`, `INTEGRATE`, `CERTIFY`, `EXECUTE`
- linked event chains through `prev_signature`
- bus publish/subscribe state
- sequence-order rejection
- deployment gate requiring written `APPROVED`
- apex execute gate requiring written `APPROVED` and a complete valid chain
- sovereignty sweep using the module-awareness compliance audit

The integrated API surface is:

- `GET /titan/health`
- `POST /titan/voice/emit`
- `POST /titan/voice/verify`
- `GET /titan/voice/chain/{chain_id}`
- `POST /titan/bus/publish`
- `POST /titan/bus/subscribe`
- `GET /titan/bus/subscribers`
- `GET /titan/bus/sequence/{chain_id}`
- `POST /titan/deploy/gate`
- `GET /titan/deploy/gates`
- `POST /titan/apex/audit/{chain_id}`
- `POST /titan/apex/execute/gate`
- `POST /titan/apex/sovereignty/sweep`

## Attack-Vector Coverage

Tests cover:

- infrastructure services excluded from sovereign module counts
- legacy voice route aliases resolved without blind forwarding
- anchor mismatch and stale URL detection
- continuity requiring both narrative and consolidation
- signed VOICE event verification
- tamper detection
- out-of-order bus event rejection
- deployment gate approval rejection
- apex rejection of incomplete event chains
- apex authorization of complete valid chains
- sovereignty sweep reuse of module-awareness compliance checks

## Production Boundary

This integration is intentionally offline-safe. It does not deploy Cloud Run services,
write Firestore documents or promote traffic. Production adapters can attach these
integrated engines to live GCP inventory, Firestore, Cloud Run IAM and Eventarc later.
