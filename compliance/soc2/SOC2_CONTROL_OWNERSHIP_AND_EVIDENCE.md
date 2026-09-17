# SARA-OMEGA SOC 2 Control Ownership and Evidence Cadence

This document converts readiness concepts into recurring operating controls. Names below are roles, not assumptions about current staffing.

| Control Area | Accountable Role | Primary Evidence | Frequency | Fail-Closed Condition |
|---|---|---|---|---|
| Access control | Security Owner | Privileged-user inventory, MFA status, access-review approval, termination evidence | Quarterly and on personnel change | Missing inventory or overdue review => `PARTIAL` |
| Change management | Engineering Owner | PR, review approval, CI run, exact commit SHA, deployment record, rollback path | Per production change | Missing review/CI/deployment binding => `BLOCKED` for release evidence |
| Vulnerability management | Security + Engineering | Dependency scan, container scan, SBOM, remediation ticket/acceptance | Per build; monthly summary | Critical unresolved finding outside approved SLA => `BLOCKED` |
| Incident response | Security Owner | Incident plan, severity classification, timeline, actions, postmortem, tabletop record | Per incident; annual exercise | No current plan or no exercise evidence => `PARTIAL` |
| Vendor management | Compliance Owner | Vendor inventory, purpose, data access, risk rating, due diligence, reassessment | Onboarding; annual | Unassessed critical vendor => `PARTIAL` or `BLOCKED` if release depends on vendor |
| Data governance | Privacy Owner | Data inventory, classification, retention/deletion rules, processor map, deletion test | Annual; on material change | Unknown sensitive-data flow => `BLOCKED` for confidentiality/privacy claim |
| Backup/recovery | Operations Owner | Backup policy, restore logs, RTO/RPO test, recovery exercise | At least annual; after material change | No successful restore evidence => `PARTIAL` |
| Security awareness | Management/Security | Training completion, policy acknowledgment, contractor controls | Onboarding; annual | Missing evidence for in-scope personnel => `PARTIAL` |
| Policy governance | Compliance/Management | Approved policies, version history, review date, exceptions | Annual | Expired policy review => `PARTIAL` |
| AI governance | AI Governance Owner | Model/provider inventory, allowed-use boundary, epistemic/adversarial test evidence, human-approval controls | Quarterly; on model/provider change | Unknown model/provider or bypass path => `BLOCKED` |
| Logging/auditability | ROAD/Operations | Immutable or integrity-protected logs, hashes, exact-SHA evidence, retention proof | Continuous; quarterly review | Evidence mismatch/staleness => `UNVERIFIED` |
| SOC 2 claim control | Compliance/Legal | Approved claim language, review record, auditor report reference when applicable | Per external claim | No independent report => must not state SOC 2 certified/compliant |

## Evidence object minimum schema

Every control-evidence record intended for ROAD should contain:

```json
{
  "control_id": "string",
  "control_owner_role": "string",
  "control_period_start": "RFC3339 timestamp",
  "control_period_end": "RFC3339 timestamp",
  "evidence_id": "string",
  "evidence_type": "string",
  "source": "string",
  "source_commit": "string|null",
  "collected_at": "RFC3339 timestamp",
  "hash": "sha256",
  "status": "PASS|PARTIAL|BLOCKED|UNVERIFIED|NOT_APPLICABLE",
  "exception_id": "string|null",
  "reviewed_by": "string|null",
  "reviewed_at": "RFC3339 timestamp|null"
}
```

## Readiness aggregation rule

A technical PASS does not override missing operating evidence. The aggregate internal state is:

- `PASS` only when all in-scope mandatory controls have current evidence for the defined observation period and no blocking exceptions.
- `PARTIAL` when controls exist but evidence is incomplete, not sustained, or an organizational dependency remains open.
- `BLOCKED` when a critical control failure creates unacceptable risk or invalidates the claimed scope.
- `UNVERIFIED` when evidence cannot be independently tied to the asserted control period/system.

External SOC 2 status remains separate and must come only from an independent CPA report.