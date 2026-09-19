# SARA-OMEGA GPT-Native Enterprise Governance Architecture

## Position

SARA-OMEGA should be GPT-native by default. Clients should interact with SARA primarily inside a governed ChatGPT Business, Enterprise, or Edu workspace, and SARA should call external services only when a capability cannot safely live inside the GPT/workspace boundary.

```text
Client -> ChatGPT Enterprise/Business -> SARA GPT -> governed instructions and policies
       -> approved Actions or apps -> external SARA services only when necessary
```

This is intentionally lighter than a standalone SaaS-first model:

```text
Client -> SARA website -> SARA servers -> SARA database -> SARA auth -> billing
       -> logs -> backups -> cloud infrastructure -> AI provider
```

Every system SARA owns becomes a control SARA must operate, monitor, document, and prove. The GPT-native architecture reduces owned infrastructure while preserving SARA's core value: governance, assurance, policy, evidence, and decision control.

## Governing Rule

Inherit controls from OpenAI where documented. Build only the controls SARA actually owns. Never duplicate infrastructure controls without a business reason.

This rule does not mean OpenAI's certifications automatically certify SARA. OpenAI's attestations cover OpenAI's services and their documented scope, not SARA's custom business practices, external APIs, databases, employee procedures, customer promises, billing, or separately hosted infrastructure.

## Control Inheritance Model

SARA may rely on documented OpenAI controls only when all of these are true:

- The client is using an eligible ChatGPT workspace plan and feature.
- The feature is inside the documented product or compliance scope.
- The workspace administrator has enabled the required controls.
- SARA does not move the relevant customer data into an external SARA-owned system.
- The SARA evidence record identifies the inherited control source and the remaining SARA-owned responsibility.

OpenAI's public security material describes business data protections such as encryption in transit and at rest, default non-training on organization data, independent audit validation, SOC 2 Type 2, ISO 27001-series certifications, and ISO/IEC 42001 AI Management System coverage for OpenAI's consumer and business AI products and models in OpenAI's role as AI producer/provider.

OpenAI's Enterprise compliance tooling also supports workspace audit and compliance workflows, including Compliance Logs Platform coverage, Admin Audit, User Authentication, Codex Usage logs, and controls around GPTs and Actions such as approved domains. These are useful inheritance anchors, but SARA must record the exact feature, plan, workspace setting, and evidence source used.

## SARA-Owned Controls

SARA owns the governance layer above the OpenAI platform. These controls remain SARA responsibilities:

- SARA Trust Governance Framework: authority boundaries, state transitions, approvals, evidence, fail-closed behavior.
- SARA AI Control Framework: model-use policy, tool authority, human approval, hallucination controls, adversarial testing, provider-change rules.
- SARA Compliance Evidence Framework: maps workspace activity, SARA receipts, and external evidence into ROAD without claiming ROAD is an independent auditor.
- SARA Enterprise AI Risk Framework: risk register, model/vendor inventory, incidents, residual-risk acceptance.
- SARA Agent Governance Framework: controls what agents can read, decide, call, modify, and escalate.
- SARA Zero-Trust AI Execution Framework: authentication never automatically grants execution authority.
- SARA AI Vendor Assurance Framework: tracks OpenAI and other providers as subservice organizations, separating inherited controls from customer-owned and SARA-owned controls.
- SARA Audit Passport: reusable evidence package for vendor reviews, procurement, SOC 2 mapping, ISO 27001, NIST AI RMF, ISO 42001, and similar frameworks.

## External-Service Minimization Policy

SARA should default to the ChatGPT workspace boundary. External SARA-hosted services require an explicit reason, such as:

- A governed voice renderer or other runtime not available natively in ChatGPT.
- A cryptographic evidence store or acceptance engine that must persist outside a conversation.
- A client-approved integration that cannot be performed with native ChatGPT workspace features.
- A regulatory or contractual need for separately retained evidence.

When external services are used, SARA must record:

- Data categories sent outside ChatGPT.
- Authentication method and token boundary.
- Retention and deletion policy.
- Audit events and receipt identifiers.
- Provider and hosting responsibilities.
- Whether the service changes the compliance boundary.

## Feature Eligibility Registry

SARA must maintain a registry for every ChatGPT/OpenAI feature it uses. Each row should answer:

| Field | Required entry |
| --- | --- |
| Feature | GPTs, Actions, apps, Compliance Logs, voice, files, connectors, Codex, etc. |
| Workspace plan | Business, Enterprise, Edu, or other eligible plan. |
| OpenAI documented scope | In scope, out of scope, early access, unknown, or plan-dependent. |
| SARA usage | What SARA uses the feature for. |
| Data classes | Customer prompts, files, logs, audio, metadata, evidence, credentials. |
| Inherited controls | OpenAI controls SARA can cite for this feature. |
| SARA-owned controls | Governance, policy, evidence, review, acceptance, or external-service controls SARA still owns. |
| Client-owned controls | Workspace configuration, user lifecycle, approvals, data classification, retention policy. |
| Evidence source | URL, workspace log source, ROAD record, SARA receipt, customer admin confirmation. |
| Status | Eligible, eligible with conditions, blocked, or pending review. |

Early-access, preview, connector, app, browser, or newly launched features must default to "pending review" until SARA confirms their product and compliance coverage.

## Shared Responsibility Model

OpenAI is the underlying AI/cloud platform for in-scope ChatGPT workspace features.

SARA is the governance, assurance, policy, evidence, and decision-control layer.

The client owns its organizational policies, workspace settings, approvals, users, identity provider, data-classification rules, and retention requirements.

An independent auditor provides external assurance. ROAD, SISO, Madhouse, and SARA receipts can organize evidence, but they do not replace an independent auditor's opinion.

## ROAD Evidence Mapping

ROAD evidence for this architecture should distinguish four evidence classes:

- Inherited OpenAI controls: documented OpenAI product/security/compliance controls, with product and feature scope.
- SARA controls: SARA policy, action, voice, receipt, governance, and fail-closed evidence.
- Client controls: workspace configuration, user assignment, domain allowlists, data-retention choices, approval records.
- Auditor controls: independent review, SOC 2/ISO/NIST mapping, findings, and management responses.

No ROAD claim may state "SARA is SOC 2 compliant because OpenAI is SOC 2." The valid claim is narrower: "For this SARA GPT-native deployment, specified platform controls are inherited from OpenAI for documented in-scope features; SARA separately operates and evidences its governance controls."

## Target Commercial Architecture

```text
OpenAI = underlying AI/cloud platform
SARA = governance, assurance, policy, evidence, and decision-control layer
Client = owner of organizational policies, users, approvals, workspace settings, and data
Independent auditor = external assurance
```

The commercial story should be that SARA helps enterprises use OpenAI-native AI safely, not that SARA replaces OpenAI's infrastructure or inherits OpenAI's certifications wholesale.

## Source Anchors

- OpenAI Security & Privacy: https://openai.com/security-and-privacy/
- OpenAI Enterprise compliance and administrative tools: https://openai.com/index/new-tools-for-chatgpt-enterprise/
