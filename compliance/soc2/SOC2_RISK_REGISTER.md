# SARA-OMEGA SOC 2 Risk Register

Status vocabulary: `OPEN`, `MITIGATING`, `ACCEPTED`, `TRANSFERRED`, `CLOSED`, `UNVERIFIED`.

This register is an internal readiness artifact. It does not represent an auditor opinion or SOC 2 attestation.

| ID | Risk | Domain | Current State | Required Control / Evidence | Owner | Review Cadence |
|---|---|---|---|---|---|---|
| R-001 | Unauthorized privileged access to production or source-control administration | Security | OPEN | Privileged-access inventory; MFA evidence; quarterly access review; joiner/mover/leaver procedure | Security Owner | Quarterly |
| R-002 | Unreviewed or unauthorized production change | Change Management | MITIGATING | PR review; exact-SHA CI; deployment approval; rollback evidence; branch protection | Engineering Owner | Per change / Quarterly review |
| R-003 | Dependency or supply-chain vulnerability reaches production | Security | MITIGATING | Dependency audit; SBOM; container scan; signed/reproducible build evidence; remediation SLA | Engineering Owner | Per build / Monthly review |
| R-004 | Security incident is not identified, escalated, contained, or documented consistently | Incident Response | OPEN | Incident-response plan; severity matrix; notification tree; tabletop exercise; incident register | Security Owner | Annual exercise / Per incident |
| R-005 | Vendor or AI provider introduces confidentiality, availability, privacy, or security risk | Vendor Management | OPEN | Vendor inventory; due-diligence record; data-flow classification; contractual/security review; annual reassessment | Compliance Owner | Annual / On change |
| R-006 | Sensitive information is retained longer than intended or handled outside documented scope | Confidentiality / Privacy | OPEN | Data inventory; classification; retention schedule; deletion test; processor/subprocessor mapping | Privacy Owner | Annual / On system change |
| R-007 | Audit or security evidence becomes stale, incomplete, mismatched to deployed code, or mutable without trace | Auditability | MITIGATING | Exact-commit evidence; hashes; ROAD registry; evidence retention schedule; exception handling | ROAD / Compliance Owner | Continuous / Quarterly review |
| R-008 | Production outage or data loss exceeds recovery objectives | Availability | OPEN | Defined RTO/RPO; backup inventory; restore test; failover/recovery exercise; incident evidence | Operations Owner | At least annual / After material change |
| R-009 | AI model/tool behavior bypasses governance or produces unsupported high-impact claims | AI Governance / Processing Integrity | MITIGATING | Runtime governance; epistemic gate; adversarial tests; human approval boundaries; provider/model inventory | AI Governance Owner | Continuous / Quarterly review |
| R-010 | Personnel or contractors lack security awareness or retain access after role termination | Security / HR | OPEN | Security training; confidentiality acknowledgment; access termination checklist; periodic review | Management / Security Owner | Onboarding / Annual / Termination |
| R-011 | Security policy exists but is not approved, reviewed, or enforced operationally | Governance | OPEN | Policy set; named owners; approval record; annual review; exception register | Management / Compliance Owner | Annual |
| R-012 | Public claims overstate SOC 2 status before independent examination | Governance / Sales | MITIGATING | Claim-control policy; approved language; ROAD fail-closed status; legal/compliance review | Compliance Owner | Per claim / Quarterly |

## Risk handling rules

1. No risk may be marked `CLOSED` solely because code exists.
2. A control must have evidence showing that it operated for the stated period.
3. `MITIGATING` means one or more controls exist but operating effectiveness is not yet fully demonstrated.
4. `ACCEPTED` requires documented management acceptance, rationale, review date, and scope.
5. `TRANSFERRED` requires evidence of the transfer mechanism, such as contractual allocation or insurance; transfer does not remove residual risk.
6. ROAD may report evidence and readiness state but may not issue an external SOC 2 opinion.

## Immediate priority

The first readiness cycle should close or materially reduce R-001, R-004, R-005, R-006, R-008, R-010, and R-011, because these are not solved by application security alone and are likely to require organizational evidence.