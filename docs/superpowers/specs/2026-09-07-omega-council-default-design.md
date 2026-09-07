# SARA-OMEGA Default OMEGA Council Design

Date: 2026-09-07
Status: Design approved in principle; implementation pending user review of this written spec.

## Purpose

Make the full OMEGA Council the mandatory reasoning path for every SARA-OMEGA request while preserving selective specialist invocation, strict separation between reasoning and execution authority, and durable tamper-evident verdict history.

## Governing Principles

1. Every request enters the OMEGA Council pipeline.
2. SARA remains the orchestration and final-synthesis layer.
3. External providers are specialists only; provider output is never treated as verified fact by default.
4. The full Council process always runs, but only relevant external specialists are invoked.
5. The Council is advisory only and never directly performs external mutations.
6. Execution requires a separate authority/policy/authentication/fail-safe path.
7. Every finalized OMEGA verdict is durably recorded.
8. Ledger history is append-only and tamper-evident.
9. Corrections create new superseding records rather than rewriting prior records.
10. Every finalized ledger verdict requires both a conventional signature and ML-DSA before acceptance.
11. Raw signing private keys must not be stored on SARA application disk; signing must use external key/KMS/HSM/secret infrastructure or an equivalently isolated signer service.
12. Signature or durable-write uncertainty fails closed.

## Mandatory Council Pipeline

Every request follows this ordered lifecycle:

Observe -> Map -> Evaluate -> Generate -> Cross-Examine -> Stress-Test -> Synthesize -> Govern -> Verdict -> Record

### Observe
Capture the user request, actor, authority context, requested action, current runtime state, and available evidence context.

### Map
Build a ProblemMap containing objective, known facts, constraints, assumptions, unknowns, risks, and subtasks.

### Evaluate
Determine evidence needs, complexity, risk level, uncertainty, contradiction exposure, and which specialist capabilities are relevant.

### Generate
Invoke only relevant specialists and collect independent SpecialistResult objects. Providers must remain isolated enough that independent analysis is preserved when independence matters.

### Cross-Examine
Compare provider claims, evidence, assumptions, dates, source quality, contradictions, and unsupported assertions. No majority-vote truth rule is allowed.

### Stress-Test
Challenge the strongest proposed conclusion, identify failure modes, check critical assumptions, and downgrade confidence when evidence is incomplete, stale, disputed, or unverifiable.

### Synthesize
SARA, not a provider, produces the candidate semantic verdict from the Council record.

### Govern
Apply governance and authority rules to the candidate verdict. Governance may ALLOW, ESCALATE, or BLOCK reasoning output, but this stage still does not execute external actions.

### Verdict
Emit the standard OMEGA Verdict contract: Decision; Why; Confidence; Council Findings; Critical Assumption; Primary Risk; Evidence Gaps; Next Action; Governance Disposition; Claims; Providers Used.

### Record
Canonicalize, hash-chain, dual-sign, verify, durably commit, and confirm the verdict ledger record before returning it as a durable OMEGA decision.

## Specialist Routing

The Council always runs internally. External specialist calls remain selective.

Initial specialist classes already present in the repository remain supported:

- Perplexity: current research/evidence
- Codex: engineering/code
- Cursor: repository analysis
- Data Analytics: datasets/statistics/BI

Routing must be capability- and need-based, not simple blanket fan-out. The router may invoke zero external specialists for a trivial request, but the request still traverses all internal Council stages. New specialist types must register through the same provider interface and cannot bypass verification or SARA synthesis.

## Reasoning vs Execution Boundary

OMEGA Council has no direct mutation authority.

Council may recommend deployments, repository changes, messages, purchases, cloud actions, database mutations, or other external operations, but it cannot perform them itself.

Any real-world execution must pass through a separately authenticated execution plane with explicit authorization, policy evaluation, idempotency protection, fail-safe controls, and audit logging. Existing GPT_ACTION_TOKEN or TEST_TOKEN roles must not be promoted into privileged execution authority merely because they can request Council reasoning.

## Durable Decision Ledger

Every finalized verdict is recorded automatically.

Each ledger entry should include at minimum:

- decision_id
- request_id/correlation_id
- timestamp
- actor and authority metadata
- canonical request digest
- ProblemMap
- specialist assignments
- specialist results or bounded references/digests where raw payload retention is disallowed
- evidence and claim verification states
- contradictions
- Council findings
- critical assumption
- primary risk
- evidence gaps
- confidence
- governance disposition
- final verdict
- providers used
- previous_record_hash
- current_record_hash
- supersedes_decision_id when applicable
- conventional signature metadata
- ML-DSA signature metadata
- signature verification status
- durable commit status

The ledger is append-only. Existing verdict records are immutable at the application layer. A correction references the earlier decision through supersedes_decision_id and preserves the full chain.

## Canonicalization and Hash Chain

Before signing, the ledger payload must be serialized through one deterministic canonicalization routine. Fields that are inherently nondeterministic must be normalized before hashing.

The record hash must bind at least:

- canonical verdict payload
- previous_record_hash
- decision_id
- timestamp
- schema/version identifier

Chain verification must be available as a runtime and testable operation. A broken chain must be surfaced as an integrity failure, never silently repaired.

## Dual-Signature Acceptance Gate

Every finalized OMEGA verdict requires two verified signatures over the same canonical record digest:

1. Conventional signature: Ed25519
2. Post-quantum signature: ML-DSA

A ledger record is accepted only when:

- canonicalization succeeds
- previous-chain state is valid
- Ed25519 signing succeeds
- ML-DSA signing succeeds
- Ed25519 verification succeeds
- ML-DSA verification succeeds
- durable write succeeds
- durable read-after-write confirmation succeeds

Failure or uncertainty in any required step produces a fail-closed non-durable result. The system must not label such a verdict as durably recorded.

## Key Custody

SARA application containers must not persist raw private signing keys on local disk.

The signing interface must abstract external key custody so deployment-specific implementations can use appropriate managed infrastructure such as AWS KMS/HSM-backed services, GCP KMS/external signer services, Azure Key Vault/Managed HSM, or another isolated signing service capable of the required algorithm.

Because managed-cloud support for ML-DSA may differ by provider and deployment date, the implementation must not fake ML-DSA support or silently downgrade. If no approved ML-DSA signer is configured, the durable-verdict gate remains unavailable/fail-closed while non-durable reasoning may be surfaced with an explicit integrity status.

Private key material, signing tokens, or credentials must never be written to the repository, logs, verdict payloads, or audit output.

## Data Flow

1. Gateway receives request.
2. Council coordinator creates request/correlation identity.
3. Observe and Map produce normalized problem context.
4. Evaluator classifies evidence/risk/specialist needs.
5. Router selects relevant specialists.
6. Specialists execute independently where required.
7. EvidenceVerifier validates and cross-compares claims.
8. Cross-examination and stress-test stages produce challenge findings.
9. SARA semantic synthesis creates candidate verdict.
10. Governance/authority evaluates the reasoning result.
11. Canonical verdict record is assembled.
12. Ledger verifies prior chain head.
13. External Ed25519 signer signs digest.
14. External ML-DSA signer signs same digest.
15. Both signatures are verified.
16. Ledger appends record transactionally.
17. Read-after-write and chain-head verification confirm durability.
18. Final response returns verdict plus integrity/durability metadata.

## Error Handling

- Specialist unavailable: continue only if the Council can truthfully characterize the resulting evidence gap; never invent the missing analysis.
- Semantic judge unavailable: retain the existing honest fallback behavior and mark synthesis limitations.
- Evidence conflict: mark disputed/unsupported status and reduce confidence rather than majority-vote resolution.
- Chain corruption: block new durable appends until explicitly repaired through a governed recovery process.
- Signer unavailable: do not accept the record as durable.
- Signature mismatch: quarantine the attempted record and emit an integrity event.
- Durable write uncertainty: return a non-durable/uncertain status and do not retry blindly if retry could create duplicate records.
- Execution requested: return the Council recommendation and hand off only to the separate execution authorization layer.

## Primary Code Boundaries

Expected implementation areas:

- app/orchestrator.py: convert solve() into the mandatory staged Council coordinator.
- app/router.py: preserve selective specialist invocation while removing the current meaning of council=False as a bypass of Council reasoning.
- app/models.py: extend Council stage, integrity, signature, durability, and supersession schemas.
- app/memory.py or a dedicated ledger module: append-only durable verdict ledger, chain head, transactional writes, recovery, chain verification.
- new signer abstraction module(s): Ed25519 and ML-DSA signer/verifier interfaces with no raw key persistence.
- app/verification.py: cross-examination/contradiction handling and evidence state integration.
- main.py: expose Council/integrity metadata through governed endpoints without granting execution authority.
- OMEGA_COUNCIL.md: align documentation with mandatory Council semantics.
- tests/: comprehensive unit, integration, failure, corruption, concurrency, and adversarial tests.

Exact file placement may change after implementation-plan-level inspection, but responsibilities must remain isolated and auditable.

## Compatibility

Existing public request models should remain backward compatible where practical. The council field may remain temporarily for schema compatibility, but setting council=false must no longer bypass the Council. It should be ignored/deprecated or interpreted only as a specialist fan-out hint if compatibility requires it; internal mandatory Council stages cannot be disabled.

Existing provider interfaces should be reused rather than replaced unnecessarily.

## Testing Requirements

Implementation is not accepted without tests covering at least:

- every request traverses every mandatory internal Council stage
- trivial request with zero external specialists still produces a Council verdict
- selective routing invokes only relevant specialists
- provider output is never promoted directly to verified truth
- Council cannot execute external mutations
- governance BLOCK and ESCALATE behavior
- deterministic canonicalization
- append-only behavior
- correction/supersession behavior
- previous-hash chain linkage
- chain-corruption detection
- concurrent append safety
- Ed25519 sign/verify success and failure
- ML-DSA sign/verify success and failure
- dual-signature mandatory gate
- signer outage fails closed
- durable-write failure and read-after-write uncertainty
- restart recovery of ledger chain head
- secret-redaction checks
- no raw private-key persistence
- existing SARA tests continue to pass

## Acceptance Criteria

The feature is complete only when all of the following are demonstrated in code and tests:

1. Every request follows the mandatory OMEGA Council lifecycle.
2. External specialists are selectively invoked by relevance.
3. SARA remains final synthesizer.
4. Council has no direct execution authority.
5. Every finalized verdict enters an append-only durable ledger.
6. Every accepted ledger record is hash-chained.
7. Every accepted ledger record has verified Ed25519 and ML-DSA signatures over the same canonical digest.
8. Private signing keys are not stored on SARA application disk or in source.
9. Failure of either required signature or durability check fails closed.
10. Corrections are represented as superseding records, never destructive rewrites.
11. Chain verification survives process restart.
12. Relevant existing and new tests pass with no governance weakening.

## Explicit Non-Goals

- The Council does not autonomously deploy, send, purchase, mutate repositories, or alter cloud state.
- This work does not grant new execution privileges to ChatGPT action/test tokens.
- This work does not treat a provider consensus as truth.
- This work does not silently downgrade from ML-DSA when PQC signing is unavailable.
- This work does not add raw private keys to environment files, repository files, logs, or local persistent application storage.
