# SARA-OMEGA SOC 2 Readiness Constitution

Version: 1.0
Status: INTERNAL READINESS STANDARD — NOT AN AUDITOR ATTESTATION
Effective baseline: 2026-09-16

## 1. Purpose

This constitution establishes the internal control, evidence, governance, and truth requirements SARA-OMEGA must satisfy before management represents the service as ready for an independent SOC 2 examination.

This document does not confer SOC 2 compliance, certification, attestation, or an auditor opinion. Only an independent qualified CPA firm can issue a SOC 2 report after performing the applicable examination procedures.

## 2. Authoritative framework

SARA-OMEGA readiness shall be mapped to the AICPA Trust Services Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy, using the currently applicable published criteria and description criteria. AI-related examination considerations shall also account for AICPA TQA Section 9561, Effect of the Service Organization's Use of AI on SOC 1 and SOC 2 Examinations, published 2026-09-11.

The initial audit target shall be Security, with Availability, Confidentiality, Processing Integrity, and Privacy added when those categories are materially included in SARA-OMEGA's customer commitments and system description.

## 3. Truth boundary

SARA-OMEGA, ROAD, Madhouse, SIOS, CI/CD, runtime health checks, or any internal subsystem MUST NOT emit or imply any of the following solely from internal evidence:

- "SOC 2 certified"
- "SOC 2 compliant"
- "SOC 2 passed"
- "SOC 2 Type I complete"
- "SOC 2 Type II complete"
- "auditor approved"

Allowed internal claims are limited to evidence-scoped statements such as:

- SOC 2 readiness control implemented
- readiness evidence verified
- control operating evidence present
- internal readiness assessment PASS/PARTIAL/BLOCKED/UNVERIFIED/NOT_APPLICABLE
- independent auditor examination pending

## 4. Control status vocabulary

Every SOC 2 readiness control shall use exactly one status:

- PASS — design is implemented and current evidence demonstrates operation for the stated period/frequency.
- PARTIAL — some required design or operating evidence exists, but the control is incomplete.
- BLOCKED — a required dependency, owner, policy, process, system, or approval is missing.
- UNVERIFIED — implementation may exist but sufficient current evidence has not been examined.
- NOT_APPLICABLE — excluded only with documented scope rationale and management approval.

No control may be promoted from PARTIAL, BLOCKED, or UNVERIFIED through inference, model judgment, vendor marketing material, or unsupported management assertion.

## 5. Mandatory control record

Each in-scope control shall have a canonical record containing:

- control_id
- Trust Services Criteria mapping
- control title
- control objective
- scope/system component
- control owner
- operator, if different from owner
- frequency
- preventive/detective/corrective classification
- manual/automated/hybrid classification
- implementation description
- evidence required
- evidence source
- evidence retention period
- test procedure
- last test date
- last test result
- exception state
- remediation owner
- remediation due date
- ROAD evidence identifier, when applicable
- exact source/deployment commit where technically relevant
- external dependency/subservice organization mapping

## 6. Evidence integrity requirements

SOC 2 readiness evidence shall be:

1. attributable — tied to an identifiable system, control, owner, and period;
2. time-bound — include timestamp and applicable operating period;
3. reproducible — another authorized reviewer can locate or regenerate it when appropriate;
4. integrity-protected — hashes, signatures, append-only storage, provider records, or equivalent safeguards are used where material;
5. scope-bound — evidence for one environment, tenant, service, commit, or provider shall not be promoted to unrelated scope;
6. retained — preserved according to the approved evidence-retention schedule;
7. reviewable — accessible to authorized management and the independent auditor;
8. secret-safe — passwords, private keys, bearer tokens, API secrets, and sensitive values are excluded from evidence packages unless an auditor specifically requires protected review.

## 7. ROAD integration

ROAD may act as the internal readiness evidence registry and release-control verifier. ROAD may verify:

- exact-SHA CI evidence
- security scans
- adversarial testing
- governance and privacy gates
- production acceptance
- deployment identity
- release approvals
- evidence hashes and freshness
- recovery test evidence
- change-management evidence
- exception/remediation closure evidence

ROAD MUST NOT act as the independent SOC 2 auditor and MUST NOT convert internal PASS states into an external SOC 2 opinion.

A future ROAD SOC 2 readiness verdict shall be expressed only as:

`SOC2_READINESS_INTERNAL = PASS | PARTIAL | BLOCKED | UNVERIFIED`

and shall carry:

`INDEPENDENT_AUDITOR_ATTESTATION = REQUIRED`

## 8. Minimum Security readiness domains

The initial Security scope shall include at minimum:

### Governance and control environment
- documented security roles and responsibilities
- management oversight
- ethics/code-of-conduct expectations
- risk assessment process
- control ownership and review cadence

### Identity and access management
- unique identities
- least privilege
- privileged-access restrictions
- MFA where appropriate
- onboarding, role change, and offboarding procedures
- periodic access review
- service-account governance
- authentication and authorization logging

### Change management
- source control
- review/approval of production changes
- CI/CD testing
- separation of development and production authority where feasible
- rollback procedures
- emergency change process
- traceability from change request to deployed commit

### Secure software and infrastructure
- dependency vulnerability scanning
- secret scanning
- secure configuration
- container/image controls
- infrastructure and application hardening
- input validation and injection defenses
- supply-chain controls
- vulnerability remediation SLAs

### Logging and monitoring
- security-relevant event logging
- access and privileged action logging
- alerting and escalation
- audit trail integrity
- log retention
- periodic review

### Incident response
- documented incident response plan
- severity classification
- triage and escalation
- containment and recovery
- evidence preservation
- customer/regulatory notification decision process
- post-incident review
- tabletop or live testing cadence

### Vendor and subservice organization management
- inventory of material vendors/subprocessors
- security/privacy due diligence
- contract/security terms where applicable
- ongoing monitoring
- dependency risk classification
- complementary subservice organization control mapping

### Business continuity and recovery
- backup strategy
- restoration testing
- recovery objectives where committed
- continuity procedures
- provider outage dependencies
- fail-safe/fail-closed behavior

### Data protection
- data classification
- encryption in transit and at rest where applicable
- retention and deletion rules
- tenant separation
- secret handling
- privacy and confidentiality commitments

## 9. AI-specific control requirements

Because SARA-OMEGA materially uses AI, readiness shall explicitly document and test controls around:

- AI/model provider inventory and dependency boundaries
- model/version identification where technically available
- system prompts, policies, tool permissions, and governance configuration changes
- prompt/tool injection defenses
- hallucination/unsupported-claim controls for material outputs
- human approval gates for high-impact actions
- model/output monitoring and exception handling
- data sent to external AI providers and associated retention/usage terms
- provider changes and model deprecations
- adversarial and misuse testing
- AI incident escalation
- evidence distinguishing deterministic controls from probabilistic model behavior

AI capability claims shall be evidence-scoped and may not substitute for operating control evidence.

## 10. Organizational controls that software cannot satisfy alone

The following require human/organizational operation even when SARA automates evidence:

- assignment of accountable control owners
- hiring/onboarding/offboarding approvals
- employee/contractor security training
- acceptable-use acknowledgment
- vendor contracting and review
- legal/privacy review
- management risk acceptance
- incident notification decisions
- business continuity leadership decisions
- auditor engagement and management assertion

A technical PASS shall not override a missing organizational control.

## 11. Control testing cadence

Controls shall define a frequency such as continuous, per-change, daily, monthly, quarterly, annually, or event-driven. Evidence must correspond to that frequency.

Type I readiness focuses on whether controls are suitably designed and implemented as of a point in time. Type II readiness additionally requires evidence that controls operated effectively throughout the examination period selected with the auditor.

## 12. Exceptions and remediation

Any failed or missed control operation shall create an exception record with:

- exception_id
- affected control
- discovery time
- evidence
- impact assessment
- compensating control, if any
- remediation action
- remediation owner
- due date
- closure evidence
- management acceptance when not immediately remediated

Exceptions may not be deleted to manufacture a clean readiness history.

## 13. Required readiness artifacts

Before independent audit fieldwork, SARA-OMEGA management should maintain at minimum:

- system description
- infrastructure/data-flow diagram
- in-scope product/service inventory
- control matrix
- risk register
- asset/vendor/subprocessor inventory
- access-control policy and reviews
- secure development/change-management policy
- vulnerability-management policy
- incident response plan and test evidence
- business continuity/disaster recovery plan and test evidence
- logging/monitoring policy
- data classification/retention/deletion policy
- privacy/confidentiality policy as applicable
- security awareness records
- exception/remediation register
- evidence index
- management readiness assertion draft for auditor review

## 14. Release interaction

Commercial production release and SOC 2 readiness are separate states.

A release may be technically accepted by ROAD while SOC 2 readiness remains PARTIAL or BLOCKED. Conversely, SOC 2 readiness evidence shall not automatically authorize a production release.

## 15. Auditor independence boundary

The independent auditor determines the examination scope, procedures, samples, sufficiency of evidence, exceptions, and opinion. SARA-OMEGA and ROAD may prepare and organize evidence, but shall not control or predict the auditor's opinion.

## 16. Change control for this constitution

Material changes to this constitution require versioning, source-control history, management approval, and an assessment of whether existing control mappings or evidence procedures must be updated.
