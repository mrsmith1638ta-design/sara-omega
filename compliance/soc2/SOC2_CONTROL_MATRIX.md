# SARA-OMEGA SOC 2 Control Matrix

Assessment date: 2026-09-16
Assessment type: Internal readiness baseline
Initial target category: Security
Secondary categories: Availability, Processing Integrity, Confidentiality, Privacy — scope pending management/customer commitments

> This matrix is an internal readiness artifact. It is not a SOC 2 report, certification, CPA opinion, or representation of compliance.

## Status legend

- PASS: implemented and current evidence reviewed for the stated internal scope
- PARTIAL: meaningful implementation/evidence exists but audit-ready design or operating evidence is incomplete
- BLOCKED: required dependency/process/owner/artifact is missing
- UNVERIFIED: implementation may exist but sufficient evidence was not reviewed
- NOT_APPLICABLE: requires documented rationale

## Baseline matrix

| ID | Readiness domain | Internal status | Current evidence / strength | Gap to audit readiness | Required next evidence |
|---|---|---|---|---|---|
| SOC2-GOV-01 | Governance and release authority | PARTIAL | ROAD verifies exact-SHA governance/release evidence and separates internal opposition/review agents from promotion authority. Control ownership/evidence cadence is now documented. | Named real-world owners and recurring management review evidence are not yet demonstrated. | Assign owners; retain quarterly review approvals. |
| SOC2-RISK-01 | Enterprise risk assessment | PARTIAL | `SOC2_RISK_REGISTER.md` now establishes an initial organization-level risk register with treatment rules. | Management approval, residual-risk decisions, and recurring review history remain outstanding. | Approved risk methodology; signed/dated review; treatment evidence. |
| SOC2-IAM-01 | Authentication and authorization | PARTIAL | Application security architecture includes authentication/authorization and fail-closed controls; protected routes and authorization boundaries have been tested. | Workforce/admin identity lifecycle, MFA policy, joiner-mover-leaver process, privileged access inventory, periodic access review not verified. | IAM policy, user/admin inventory, MFA evidence, access review, offboarding test. |
| SOC2-IAM-02 | Least privilege / privileged access | PARTIAL | SARA architecture enforces scoped authority and no automatic promotion authority for review agents. | Human/cloud privileged roles and service accounts are not mapped into a recurring review process. | Privileged role matrix, service account register, quarterly review evidence. |
| SOC2-CHG-01 | Source/change control | PARTIAL | GitHub source control, exact-commit CI, validation runs, deployment identity, and release evidence are present. | Main branch is not currently protected; formal emergency-change procedure and segregation-of-duties evidence remain incomplete. | Protect branch; require review/status checks; emergency change procedure; change samples. |
| SOC2-CICD-01 | Automated build/test/security gate | PASS (technical scope) | Exact-SHA CI, dependency audit, tests, compile, adversarial gate, container build, ROAD MCP validation, and SBOM generation are evidenced. | Evidence retention period and auditor sampling/export process need formalization. | Retention policy, evidence index, periodic completeness review. |
| SOC2-VULN-01 | Vulnerability management | PARTIAL | Dependency auditing and security validation execute in CI. | Full severity SLAs, infrastructure/container scanning cadence and remediation register are not fully evidenced. | Vulnerability policy, severity/SLA table, findings/remediation history. |
| SOC2-SEC-01 | Application-native security | PASS (internal technical design) | ROAD SECURITY reports exact-source technical evidence and SARA uses fail-closed/security/adversarial controls. | Auditor still needs scoped control description and operating samples over the audit period. | Control narrative, population, samples, exceptions. |
| SOC2-LOG-01 | Security logging and audit trail | PARTIAL | SARA has audit receipts/ledgers and ROAD evidence hashes. | Central event coverage, retention, alerting, review cadence and log-access controls are not fully verified. | Logging standard, event catalog, retention config, alert samples, review record. |
| SOC2-MON-01 | Security monitoring and escalation | PARTIAL | Runtime health, ROAD gates and adversarial evidence provide technical monitoring signals. | Operator escalation procedure, alert ownership and incident linkage are not yet evidenced over time. | Monitoring runbook, routing, escalation test, incident/ticket samples. |
| SOC2-IR-01 | Incident response | PARTIAL | `INCIDENT_RESPONSE_PLAN.md` now defines severity, lifecycle, evidence, authority boundaries, and exercise expectations. | No tabletop/real incident operating evidence has yet been retained for this readiness cycle. | Tabletop report, corrective actions, incident register. |
| SOC2-BCP-01 | Business continuity | PARTIAL | ROAD RECOVERY reports configured fail-safe, persistence, and retained chain for the deployed candidate. | Organization-level continuity plan, business impact analysis, dependency scenarios and customer communications are not verified. | BIA, BCP, outage exercise, lessons/remediation. |
| SOC2-DR-01 | Backup/restore and recovery testing | PARTIAL | ROAD recovery evidence demonstrates technical recovery attributes for the exact deployment. | Defined RTO/RPO, backup scope, restoration frequency and retained restore-test records require formalization. | Backup standard, RTO/RPO approvals, restore-test evidence. |
| SOC2-VEND-01 | Vendor/subservice organization management | PARTIAL | `VENDOR_AND_SUBPROCESSOR_MANAGEMENT.md` now defines inventory fields, risk tiers, due diligence, AI-provider additions and reassessment requirements. | Real vendor inventory and completed due-diligence records have not yet been populated. | Vendor register, subprocessor list, due diligence, reports/terms review, annual reassessment. |
| SOC2-DATA-01 | Data classification | PARTIAL | `DATA_CLASSIFICATION_RETENTION.md` now defines Restricted/Confidential/Internal/Public handling baseline and required inventory fields. | Production assets have not yet been fully inventoried/classified. | Complete data inventory and handling matrix. |
| SOC2-ENC-01 | Encryption / protected transport | PARTIAL | Production interactions are HTTPS and secret-bearing fields are excluded from ROAD artifacts. | At-rest encryption and key-management responsibilities across all stores/providers are not comprehensively mapped. | Encryption standard, provider configs, key ownership/rotation evidence. |
| SOC2-RET-01 | Retention and deletion | PARTIAL | `DATA_CLASSIFICATION_RETENTION.md` defines purpose-bound retention and deletion evidence requirements. | Approved retention periods and tested production deletion evidence remain outstanding. | Retention schedule, deletion SOP, sample deletion test, backup retention mapping. |
| SOC2-PRIV-01 | Privacy commitments | PARTIAL | A SARA privacy notice exists and ROAD currently reports internal PRIVACY gate PASS for the exact deployed candidate. | Full data map, rights handling, processor mapping and contractual commitments are not established by this baseline. | Data map, subprocessor list, request/incident procedures, privacy owner approval. |
| SOC2-CONF-01 | Confidentiality | PARTIAL | Secret isolation and evidence redaction/scoping are part of SARA's technical design; classification baseline now exists. | Confidential-information inventory, contractual classifications, access reviews and disposal requirements are not fully mapped. | Inventory, handling/access evidence, disposal records. |
| SOC2-PI-01 | Processing integrity | PARTIAL | Exact-source verification, evidence-bound gates, deterministic governance components and claim-integrity controls provide strong technical foundations. | Customer-facing processing commitments, completeness/accuracy criteria, error handling and period evidence need formal scope. | Processing commitments, validation rules, exception logs, sample reconciliations. |
| SOC2-AI-01 | AI provider/model inventory | PARTIAL | Vendor policy now explicitly requires model/service identifiers, data terms, authority, update behavior and retention characteristics. | Real provider/model inventory remains to be populated and reviewed. | AI system/provider inventory and dependency register. |
| SOC2-AI-02 | AI change/configuration governance | PARTIAL | Source-controlled governance, tool routing, release gates and exact-SHA evidence exist. | Model/provider version changes and non-code AI configuration changes need formal change records and review rules. | AI change policy, provider/model change log, approval samples. |
| SOC2-AI-03 | AI adversarial/misuse testing | PASS (technical scope) | ROAD recognizes Madhouse adversarial review for the exact deployed source while preserving no execution/promotion authority. | A recurring SOC 2 control cadence, population definition and retained exceptions/remediation evidence are needed. | Quarterly/per-release test plan, evidence index, exception records. |
| SOC2-AI-04 | AI output/claim governance | PASS (technical scope) | ROAD recognizes an exact-commit epistemic claim audit; SARA architecture includes fail-closed unsupported-claim controls. | Audit scope must define which outputs are relied upon and how exceptions/human review operate over time. | Output-risk classification, sample review records, exception handling. |
| SOC2-AI-05 | AI data-use/privacy boundary | PARTIAL | Privacy/evidence controls avoid secret-bearing fields; vendor policy now requires provider data-use and model-change review. | Provider-by-provider data use, training, retention, residency and subprocessors must be documented. | Provider data-use matrix, DPAs/terms evidence, annual review. |
| SOC2-HR-01 | Personnel security / onboarding / offboarding | BLOCKED | Not a software-only control. | No approved personnel security lifecycle evidence was reviewed. | Onboarding checklist, confidentiality terms, training, termination access-revocation evidence. |
| SOC2-TRAIN-01 | Security awareness training | BLOCKED | Not evidenced in repository/ROAD baseline. | Recurring security/AI acceptable-use training and acknowledgment needed for personnel in scope. | Training policy, completion roster, annual evidence. |
| SOC2-POL-01 | Policy governance | PARTIAL | SOC 2 constitution, control matrix, ownership/evidence policy, incident plan, vendor policy, data policy and risk register now exist. | Formal management approval, version register, annual review history, exception process remain to be operated. | Policy register, owner approvals, review/exception evidence. |
| SOC2-EVID-01 | Evidence integrity and traceability | PASS (technical scope) | ROAD keeps evidence IDs, hashes, timestamps, exact deployed source and gate-specific details; control-evidence minimum schema is now defined. | SOC 2 evidence-retention, completeness checks and auditor export/index procedure need operational evidence. | Evidence SOP, retention schedule, quarterly completeness check. |
| SOC2-EXT-01 | Independent CPA examination | BLOCKED | Internal readiness work can prepare the environment. | Independent examination has not been performed by virtue of internal ROAD/GitHub evidence. | Auditor selection, scope letter, readiness review, examination period, final report. |

## Baseline conclusion

SARA-OMEGA now has both a meaningful technical foundation and an initial operating-control framework. The strongest areas are exact-source CI/CD evidence, security gating, adversarial/epistemic review, production attestation, recovery evidence, evidence integrity, documented risk treatment structure, incident-response design, vendor-governance design, and data-classification/retention design.

The dominant remaining gaps are operating evidence and organizational implementation: privileged-access lifecycle, branch protection/review enforcement, management approvals, vendor inventory/due diligence, complete production data inventory, tested deletion, incident/tabletop evidence, continuity/restore objectives, personnel controls, training, and sustained control operation across the intended audit period.

Current internal state:

`SOC2_READINESS_INTERNAL = PARTIAL`

Independent SOC 2 status remains separate and requires an independent CPA examination/report.