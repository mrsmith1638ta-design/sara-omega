# SARA-OMEGA V3.2.1 Release Notes

## Added

- Railway zero-to-production provisioning from an empty Railway account.
- Automated project and service creation.
- Automated persistent `/data` volume creation.
- Automated fail-safe master-key generation without printing the key.
- Production bootstrap controller before Uvicorn startup.
- Encrypted checkpoint self-test and retained-chain verification.
- Two-boot persistence proof before production acceptance.
- Public and owner-only production-acceptance endpoints.
- GitHub Actions validation and deployment automation.
- Runtime-visible `3.2.1` release identity while preserving v2.5.2 provenance.

## Security posture

All mandatory security gates remain fail-closed. Provider or deployment automation does not create epistemic or execution authority. Restored state does not bypass current authentication or execution policy.
