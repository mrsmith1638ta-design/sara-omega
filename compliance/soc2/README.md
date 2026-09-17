# SARA-OMEGA SOC 2 Readiness Package

This directory contains SARA-OMEGA's internal SOC 2 readiness baseline. It is designed to support a future independent SOC 2 examination; it does not represent certification or an auditor opinion.

## Included artifacts

- `SOC2_READINESS_CONSTITUTION.md` — truth boundary, evidence requirements, control governance, AI-specific requirements, and auditor-independence rules.
- `SOC2_CONTROL_MATRIX.md` — initial internal gap assessment against SOC 2 readiness domains.
- `soc2-readiness-status.json` — machine-readable status intended for future ROAD ingestion.

## Current baseline

`SOC2_READINESS_INTERNAL = PARTIAL`

`INDEPENDENT_AUDITOR_ATTESTATION = REQUIRED`

Current technical strengths include exact-SHA CI/CD evidence, security and governance gates, adversarial review, epistemic review, production acceptance, recovery evidence, and evidence integrity. The principal remaining work is organizational and operational.

## Execution sequence

### Phase 1 — Scope and ownership

1. Define the legal/service organization that will be examined.
2. Define the in-scope SARA service and production boundary.
3. Select Security as the initial Trust Services Category; add other categories only where customer commitments justify them.
4. Name an accountable owner for every control.
5. Approve the SOC 2 readiness constitution.
6. Create the evidence-retention and exception-management procedures.

Exit criterion: every in-scope control has an owner, frequency, evidence requirement, test method, and scope statement.

### Phase 2 — Organizational control build

Implement and approve:

- information security policy
- enterprise risk assessment and risk register
- identity/access lifecycle procedure
- privileged access review
- change-management procedure
- vulnerability-management policy and remediation SLAs
- logging/monitoring standard
- incident-response plan
- business continuity/disaster recovery plan
- vendor/subservice organization management procedure
- data classification/retention/deletion policy
- security awareness and AI acceptable-use training
- AI provider/model/data-use inventory and review procedure

Exit criterion: no required Security-domain control remains BLOCKED solely because a policy, owner, process, or inventory is absent.

### Phase 3 — Automate evidence into ROAD

ROAD should ingest or reference evidence for controls that can be automated, including:

- GitHub change/approval records
- exact-SHA CI results
- dependency/container/security scan results
- deployment identity
- access review completion receipts where safely integrated
- vulnerability remediation evidence
- recovery/restore test evidence
- incident/tabletop exercise receipts
- vendor review timestamps/status
- control exceptions and remediation closures
- AI model/provider change records

ROAD must preserve the constitutional truth boundary and emit only internal readiness state.

Exit criterion: each automatable control produces stable evidence IDs, timestamps, scope, integrity metadata, and freshness state.

### Phase 4 — Readiness testing

Run a complete internal readiness review using the same discipline expected during external fieldwork:

- validate system description against reality
- sample control operations by frequency
- trace samples to source evidence
- record every exception
- remediate or formally accept exceptions
- verify evidence retention
- verify no evidence depends on unsupported claims
- confirm subservice organization dependencies and complementary controls

Exit criterion: all required controls are PASS internally or have documented exceptions acceptable for auditor discussion.

### Phase 5 — Independent examination

1. Engage an independent CPA firm experienced with SaaS/AI service organizations.
2. Confirm final Trust Services Category scope and system boundary.
3. Resolve readiness-review findings.
4. For Type I, establish design/implementation as of the selected date.
5. For Type II, operate controls consistently through the auditor-agreed examination period.
6. Provide the auditor evidence directly from authoritative sources/ROAD indexes without altering historical exceptions.

Final authority: the independent CPA firm's report, not ROAD.

## Priority order from this baseline

1. Enterprise risk assessment and risk register.
2. Control owner assignment and management review process.
3. IAM/privileged-access lifecycle and periodic access review.
4. Incident-response plan plus tabletop exercise.
5. Vendor/subservice organization inventory and due diligence.
6. Data classification, retention, deletion, confidentiality and privacy mapping.
7. Security/AI acceptable-use training.
8. AI provider/model/data-use inventory.
9. Formal evidence retention and exception/remediation procedures.
10. Auditor readiness review and examination planning.
