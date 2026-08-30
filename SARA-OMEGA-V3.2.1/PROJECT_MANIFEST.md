# SARA-OMEGA V.3.2.1 — Project Manifest

**Canonical release:** SARA-OMEGA V.3.2.1  
**Release version:** `3.2.1`  
**Repository:** `mrsmith1638ta-design/sara-omega`  
**Runtime provenance retained:** SARA OMEGA v2.5.2  
**Hardening lineage:** SIOS-V3.2-FAILSAFE-1

## What changed in V3.2.1

V3.2.1 promotes the V3.2 hardening architecture into a zero-to-production deployment release. It adds automated Railway account provisioning, project/service creation, persistent `/data` volume provisioning, fail-safe secret generation, production bootstrap enforcement, two-boot persistence proof, live production acceptance evidence, and automated CI validation.

The V3.2 cryptographic and epistemic hardening lineage is retained. V3.2.1 is a patch release, not a replacement architecture.

## Version semantics

- **3.2** — SIOS fail-safe and epistemic hardening architecture.
- **3.2.1** — production automation, deployment acceptance, persistence proof, and visible release identity.
- **2.5.2** — historical runtime base provenance only; it is no longer the public release version.

## Production status rule

The release must not be represented as live-production accepted until the Railway service passes health, readiness, encrypted checkpoint, retained-chain verification, and cross-boot persistence checks.
