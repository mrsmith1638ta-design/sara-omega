# API and MCP Evidence

Technical API, agent, MCP, Cursor, and Codex support is **VERIFIED** as capability evidence. It does not establish SARA-OMEGA commercial authorization.

## Evidence ledger schema

```yaml
vendor: string
source_url: string
document_title: string
retrieved_at: ISO-8601 datetime
effective_date: ISO-8601 date-or-null
terms_version: string
sha256_content_hash: lowercase-64-hex
claim: string
evidence_excerpt_reference: string
epistemic_classification: VERIFIED|SUPPORTED|INFERRED|DISPUTED|UNVERIFIED|UNKNOWN|CURRENTLY_INACCESSIBLE
authorization_scope: [string]
superseded_by: string-or-null
reviewer: string
approval_state: PENDING|APPROVED|REJECTED|SUPERSEDED
```
