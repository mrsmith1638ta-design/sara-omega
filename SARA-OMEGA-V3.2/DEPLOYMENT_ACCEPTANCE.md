# SARA-OMEGA V.3.2 — Railway Acceptance Gate

The source installation and local security validation are complete. The deployment is not declared runtime-accepted until all checks below pass against the actual Railway URL.

1. `GET /` returns SARA OMEGA successfully.
2. `GET /health` returns healthy and reports the expected hardening profile.
3. `GET /health/ready` succeeds only when mandatory runtime requirements are available.
4. `GET /admin/failsafe/status` succeeds with owner authorization and reports fail-safe enabled when production-required mode is active.
5. `POST /admin/failsafe/checkpoint` creates an encrypted checkpoint on persistent storage.
6. Restart/redeploy preserves the checkpoint on the Railway volume.
7. `POST /admin/failsafe/restore-latest` restores a verified snapshot but does not bypass current authorization or epistemic policy.
8. Corrupted/tampered latest snapshot is rejected or safely falls back to a prior valid snapshot.
9. Invalid owner/test credentials fail closed.
10. SIOS dispatch remains disabled unless the approved HTTPS endpoint and token provider are configured.

**Current status:** PENDING — live Railway service URL is not available in the repository or connected deployment metadata.
