# SARA-OMEGA SOC 2 Business Continuity / RTO / RPO Baseline

Assessment date: 2026-09-17
Control focus: SOC2-BCP-01 / SOC2-DR-01
Status: PARTIAL

> This document establishes the control framework. RTO/RPO values are not declared as achieved until management approves targets and restore/failover testing demonstrates them.

## Critical service classes

| Service class | Examples | Impact if unavailable | Target status |
|---|---|---|---|
| Governance/evidence plane | ROAD evidence and release-readiness functions | Release/readiness decisions cannot be trusted or advanced | Critical |
| Production application runtime | SARA-OMEGA hosted service endpoints | Customer/service interruption | Critical |
| Source/CI plane | GitHub repository and Actions | Changes/releases delayed; evidence generation impaired | High |
| External AI/model/tool providers | OpenAI and other routed providers | Capability degradation or feature-specific outage | High/Critical by workflow |
| Voice subsystem | Piper/voice service where enabled | Voice unavailable while core non-voice functions may remain | Medium/High |

## Required continuity design

1. Management-approved RTO and RPO per critical service class.
2. Documented backup scope, frequency, encryption, retention, and ownership.
3. Restore procedures that do not depend on undocumented operator knowledge.
4. Dependency outage scenarios covering GitHub, Railway, AI providers, DNS, secrets, and evidence stores.
5. Fail-closed behavior where evidence or authority dependencies are unavailable.
6. Customer/internal communication procedures for material outages.
7. At least annual continuity/tabletop exercise and periodic restore testing.
8. Corrective actions tracked to closure.

## Current evidence

- ROAD recovery evidence previously demonstrates configured technical fail-safe/persistence attributes for the deployed candidate.
- CI verifies production bootstrap, container build, and ROAD MCP behavior for the SOC 2 branch.
- These facts do not by themselves prove an organization-level RTO/RPO or successful restore within a defined time objective.

## Current gaps

- Approved RTO values: UNVERIFIED / NOT YET APPROVED
- Approved RPO values: UNVERIFIED / NOT YET APPROVED
- Complete backup inventory: UNVERIFIED
- Timed restore test: NOT YET EVIDENCED
- Dependency outage exercise: NOT YET EVIDENCED
- Customer communication exercise: NOT YET EVIDENCED

## ROAD state

`SOC2_BCP_DR = PARTIAL`

PASS requires approved objectives and retained evidence that recovery procedures actually meet those objectives over the selected audit period.