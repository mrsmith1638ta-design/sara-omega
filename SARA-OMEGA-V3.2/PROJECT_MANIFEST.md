# SARA-OMEGA V.3.2 — Project Manifest

**Canonical project name:** SARA-OMEGA V.3.2  
**Repository:** `mrsmith1638ta-design/sara-omega`  
**Deployment platform:** Railway (configured through `railway.json`)  
**Runtime base retained:** SARA OMEGA v2.5.2  
**Installed hardening profile:** SIOS-V3.2-FAILSAFE-1

## Project assignment

This project folder is the canonical project package for the current SARA-OMEGA V.3.2 infrastructure. The deployable repository root remains structurally compatible with Railway; this package groups the complete tested source, V3.2 hardening controls, fail-safe backup controller, validation evidence, and release metadata under one project identity without relocating runtime entrypoints.

## Included infrastructure

- Railway runtime entrypoint and deployment configuration.
- FastAPI SARA OMEGA application.
- Epistemic authority gate.
- Hardened SARA -> SIOS relay.
- AES-256-GCM fail-safe save/restore controller.
- Pre-mutation, exception, shutdown, and manual checkpoint integration.
- Owner-only checkpoint/status/restore interfaces.
- Unit/regression tests.
- Focused adversarial security gate and reports.
- Standalone hardening patch and save-controller artifacts.

## Production activation requirements

- `SARA_FAILSAFE_MASTER_KEY_HEX` or `SARA_FAILSAFE_MASTER_KEY_B64` must be supplied through the deployment secret store.
- `SARA_FAILSAFE_REQUIRED=true` is recommended for production.
- `SARA_FAILSAFE_ROOT=/data/sara-failsafe` must point to durable mounted storage.
- SIOS relay remains inactive until a real HTTPS SIOS endpoint and trusted token provider are configured.

## Runtime acceptance status

Local integration validation passed before repository installation. Live Railway HTTP verification remains **PENDING** because no public Railway endpoint is stored in the repository or recoverable from prior project records. Do not treat deployment as runtime-accepted until health, readiness, fail-safe status, checkpoint, and restore checks pass against the actual Railway service URL.
