# SARA-OMEGA SOC 2 Privileged Access Review

Assessment date: 2026-09-17
Control focus: SOC2-IAM-01 / SOC2-IAM-02
Status: PARTIAL

> This is an internal readiness artifact, not a SOC 2 attestation.

## Verified facts

- Repository owner account `mrsmith1638ta-design` has `admin` permission on `mrsmith1638ta-design/sara-omega`.
- The repository default branch is `main`.
- At the time of this review, `main` is not protected and required status checks are not enforced.
- The ChatGPT Codex Connector used for this work has repository-scoped permissions including contents/workflows/actions writes, but does not expose an administrative branch-protection mutation in the current tool surface.

## Current control conclusion

Technical access boundaries exist inside SARA, but the workforce/admin access lifecycle is not audit-ready. The current GitHub owner/admin role is a high-privilege access path and must be governed explicitly.

## Required control design

1. Maintain a privileged-access inventory covering GitHub, Railway, model/API providers, DNS, secrets stores, cloud accounts, billing, and any production database or storage service.
2. Require MFA for all privileged human accounts where supported.
3. Prohibit shared privileged human accounts.
4. Require unique service identities for automation.
5. Document business justification and owner for every privileged role.
6. Review privileged access at least quarterly and on personnel/role changes.
7. Revoke unneeded access promptly and retain evidence of revocation.
8. Record emergency/break-glass access separately and review after use.
9. Bind review evidence to ROAD without allowing ROAD to grant access.

## Evidence still required

- MFA status for each privileged human account: UNVERIFIED
- Complete collaborator/member list: UNVERIFIED
- Railway privileged-user/service-token inventory: UNVERIFIED
- Model/API provider admin inventory: UNVERIFIED
- Quarterly access review approval: NOT YET OPERATED
- Joiner/mover/leaver evidence: NOT YET OPERATED

## ROAD state

`SOC2_IAM_PRIVILEGED_ACCESS = PARTIAL`

PASS is prohibited until the privileged inventory is complete, MFA/identity controls are verified, and at least one recurring access review has been performed and retained.