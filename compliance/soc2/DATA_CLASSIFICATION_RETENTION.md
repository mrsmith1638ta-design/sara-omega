# SARA-OMEGA Data Classification and Retention Baseline

## Purpose
Define the minimum governance needed to know what SARA-OMEGA processes, where it flows, who can access it, how long it is retained, and how deletion is verified.

## Classification levels
- **Restricted:** credentials, private keys, authentication tokens, regulated/sensitive personal data, confidential customer secrets, incident forensics containing secrets.
- **Confidential:** nonpublic customer content, internal architecture, contracts, proprietary business records, nonpublic audit evidence.
- **Internal:** operational metadata and internal documentation not intended for public release.
- **Public:** information approved for unrestricted disclosure.

## Core rules
1. Restricted secrets must not be committed to source control or embedded in ROAD evidence artifacts.
2. Every production data store/log/evidence repository must have an owner and classification.
3. Retention must be purpose-bound; "retain forever" requires an explicit documented justification.
4. Deletion must address primary stores, logs, caches, backups, and third-party processors according to applicable technical and contractual limits.
5. Customer-facing commitments must not promise deletion behavior that cannot be demonstrated.
6. AI/model providers must be included in the data-flow inventory where prompts, outputs, embeddings, files, telemetry, or metadata are sent externally.

## Required data inventory fields
`data_asset_id`, name, classification, categories, purpose, source, storage_location, system_owner, authorized_roles, encryption_at_rest, encryption_in_transit, retention_period, deletion_method, backup_retention, processors_subprocessors, cross_border_flow, customer_contract_dependency, legal_hold_override, last_reviewed_at.

## Evidence required for readiness
- Completed production data-flow inventory
- Retention schedule approved by accountable owner
- At least one tested deletion workflow for applicable in-scope data
- Evidence of secret-isolation controls
- Processor/subprocessor mapping
- Backup-retention and restoration interaction documented
- Exceptions register for technical/legal retention constraints

## Current readiness state
`PARTIAL`: repository privacy boundaries and secret-exclusion principles exist, but full production data inventory, retention schedule, and tested deletion evidence remain organizational dependencies.