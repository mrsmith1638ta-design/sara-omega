# SARA-OMEGA SOC 2 Vendor and Subprocessor Register

Assessment date: 2026-09-17
Control focus: SOC2-VEND-01 / SOC2-AI-01 / SOC2-AI-05
Status: PARTIAL

> This is an internal vendor inventory baseline. Inclusion does not mean a vendor has passed due diligence. Contract, security, privacy, retention, residency, and subprocessor evidence must be reviewed separately.

| Provider / service | Known role | Risk tier | Data interaction | Due-diligence state | Required next evidence |
|---|---|---:|---|---|---|
| GitHub | Source control, CI/CD, artifacts | High | Source, workflow metadata, build/test logs, SBOM artifacts | PARTIAL | Current security/compliance reports as applicable, account security settings, retention settings, privileged-access review |
| Railway | Production hosting/runtime | Critical | Runtime configuration, service traffic, operational logs/metadata | PARTIAL | Account/admin inventory, encryption/backup/logging configuration, region/residency, incident/subprocessor documentation, contractual terms |
| OpenAI / ChatGPT integration | AI interaction/action client and model services depending on workflow | Critical | Prompt/context/action data depending on feature | PARTIAL | Provider data-use/retention terms, enterprise/account settings if applicable, subprocessors, residency, incident process, change ownership |
| Context.dev | Authorized external service/integration within documented scope | High | Scope-specific metadata/content depending on enabled integration | PARTIAL | Current contract/terms, security/privacy due diligence, retention behavior, subprocessor list, annual review record |
| Other model/API providers referenced by SARA routing | AI/model/tool processing | Critical | Workflow-dependent prompt/context/tool data | UNVERIFIED | Complete provider list, model/version inventory, data-use/retention terms, DPAs where needed, fallback/change controls |

## Required vendor lifecycle

1. Inventory before production use.
2. Assign risk tier based on service criticality, access, data sensitivity, and substitutability.
3. Review security/privacy documentation before approval for High/Critical vendors.
4. Record owner, business purpose, data categories, regions, retention, subprocessors, and contract/DPA status.
5. Monitor material terms, incidents, ownership changes, and security posture at least annually for High/Critical vendors.
6. Require documented approval for material AI/model-provider changes.
7. Maintain an exit/portability plan for Critical vendors where commercially reasonable.
8. Preserve review evidence for auditor sampling.

## ROAD state

`SOC2_VENDOR_MANAGEMENT = PARTIAL`

No provider may be treated as fully approved solely because its integration technically works or ROAD has verified runtime authorization.