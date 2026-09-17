# SARA-OMEGA SOC 2 Production Data-Flow Inventory

Assessment date: 2026-09-17
Control focus: SOC2-DATA-01 / SOC2-PRIV-01 / SOC2-CONF-01 / SOC2-AI-05
Status: PARTIAL

> This inventory records currently evidenced flows and explicitly marks unknowns. It must not be treated as a complete privacy data map until all providers and storage paths are verified.

## Known flow classes

| Flow | Source | Destination | Data class | Purpose | Retention status | Current evidence state |
|---|---|---|---|---|---|---|
| ChatGPT action status requests | ChatGPT integration | SARA-OMEGA production HTTPS endpoints | Operational metadata | Runtime/readiness attestation | Endpoint-specific; secrets excluded | SUPPORTED |
| GitHub CI execution | GitHub repository | GitHub Actions runners/artifacts | Source, build logs, dependency/SBOM metadata | Validation and release evidence | GitHub-configured artifact retention | VERIFIED for current SOC 2 branch SBOM artifact |
| ROAD evidence | SARA runtime / CI | ROAD registry/runtime endpoints | Control/evidence metadata, hashes, timestamps, exact SHA | Governance/release/readiness evidence | Retention policy requires formalization | VERIFIED technically / PARTIAL operationally |
| Railway runtime | Deployment source/config | Railway-hosted SARA services | Application/runtime/configuration metadata; customer data scope requires verification | Production service delivery | Provider/account configuration not fully inventoried | PARTIAL |
| AI/model provider calls | SARA tool/model routing | External AI/model providers | Prompt/context/tool payload varies by workflow | AI processing | Provider-specific terms and retention require inventory | UNVERIFIED as a complete map |

## Mandatory classification rules

- PUBLIC: intentionally public material.
- INTERNAL: operational material not intended for public release.
- CONFIDENTIAL: business/customer information requiring access controls.
- RESTRICTED: secrets, credentials, private keys, authentication tokens, highly sensitive personal/customer data, or regulated data requiring strongest handling.

RESTRICTED data must never be inserted into ordinary evidence artifacts or logs unless specifically required, encrypted, access-controlled, and approved.

## Required completion work

1. Enumerate every production endpoint and backing store.
2. Identify whether request/response bodies are persisted and where.
3. Map logs, traces, metrics, backups, queues, caches, and temporary storage.
4. Map every AI/model/tool provider and the exact data categories transmitted.
5. Verify provider retention/training settings and contractual terms.
6. Map geographic processing/residency where material.
7. Map deletion propagation into primary stores, logs, backups, and third parties.
8. Identify subprocessors for each production flow.

## Current truth boundary

The current privacy notice supports the claim that designated read-only status endpoints are designed not to require or return secret values. That does not establish a complete production data inventory for all SARA capabilities.

## ROAD state

`SOC2_PRODUCTION_DATA_MAP = PARTIAL`

PASS requires a complete, owner-approved inventory tied to verified provider configurations and retained review evidence.