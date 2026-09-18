# SARA-OMEGA Vendor and Subprocessor Management

## Objective
Identify and manage third parties that can materially affect SARA-OMEGA security, availability, confidentiality, privacy, processing integrity, or AI governance.

## Vendor record minimum fields
`vendor_id`, legal_name, service, business_owner, technical_owner, data_access, data_categories, production_dependency, privileged_access, subprocessor_role, hosting_region, security_documents_reviewed, contract_status, DPA_status, breach_notification_terms, deletion_return_terms, availability_dependency, risk_rating, approval_status, approved_by, approved_at, last_reviewed_at, next_review_due.

## Risk tiers
- **Critical:** can affect production execution, store/process customer-sensitive data, hold privileged access, or materially affect availability.
- **High:** significant integration or confidential data exposure without direct production control.
- **Moderate:** limited operational dependency or low-sensitivity data.
- **Low:** no meaningful system/data dependency.

## Required due diligence for Critical/High vendors
1. Define business purpose and precise system/data access.
2. Review security/privacy documentation appropriate to risk, including independent reports where available.
3. Review breach-notification, confidentiality, deletion/return, availability, and subprocessor terms.
4. Record known security or availability exceptions and mitigating controls.
5. Identify exit/continuity strategy for critical dependencies.
6. Approve before production use where feasible; emergency exceptions require documented time-bounded approval.
7. Reassess at least annually and upon material service, security, ownership, data-flow, or contract change.

## AI/model provider additions
For external AI/model/tool providers, also record model/service identifiers, data-retention/training terms, tenant isolation assumptions, tool/function authority, model-update behavior, content logging, output limitations, and whether provider changes can occur without SARA deployment changes.

## Evidence rule
A vendor is not `ASSESSED` merely because it is well-known or publishes a SOC report. SARA must retain evidence of the review decision applicable to its own use case and scope.

## ROAD state
`UNVERIFIED` until a real vendor inventory is populated and reviewed. ROAD may ingest vendor-review evidence but must not infer approval from provider reputation alone.