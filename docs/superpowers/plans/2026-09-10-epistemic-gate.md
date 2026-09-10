# Epistemic Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exact-commit-bound Epistemic claim audit that detects overstated or contradicted release claims and drives ROAD's EPISTEMIC gate.

**Architecture:** ROAD will submit a bounded claim set derived from its evidence registry to SARA's Epistemic endpoint. The endpoint will return a structured claim ledger with original claim, evidence scope, epistemic state, and corrected claim. ROAD will accept EPISTEMIC only from a valid artifact tied to the live deployed source commit; it will never infer PASS from raw test counts or model confidence.

**Tech Stack:** TypeScript, Node 20, Express, MCP, Zod, Node test runner, existing Python FastAPI service.

**Spec:** Approved in chat on 2026-09-10.

## Global Constraints

- EPISTEMIC audits claims about evidence, not source-code quality.
- Every Epistemic artifact must identify the exact deployed `source_commit_sha`.
- `OVERSTATED`, `CONTRADICTED`, malformed, missing, or stale evidence cannot produce EPISTEMIC PASS.
- ROAD remains read-only and cannot promote or execute a release.
- Existing Madhouse authority boundaries remain unchanged.

### Task 1: Define the Epistemic claim contract and failing tests

**Files:**
- Create: `road-mcp/src/epistemicEvidence.ts`
- Test: `road-mcp/tests/test-evidence.test.mjs`

**Interfaces:**
- `EPISTEMIC_EVIDENCE_ID`
- `buildEpistemicEvidence(fetchAttestation, fetcher)`
- `computeEpistemicEvidence(attestation, fetcher)`
- `EpistemicEvidenceRecord` compatible with `EvidenceRecord`

- [ ] Write tests for exact-SHA binding, claim scope correction, blocked/overstated results, and malformed artifacts.
- [ ] Run the focused test and confirm it fails because the Epistemic module is absent.
- [ ] Implement the smallest bounded JSON fetch and claim-ledger validation needed by those tests.
- [ ] Run the focused test and confirm it passes.
- [ ] Commit the contract and unit tests.

### Task 2: Add the live SARA Epistemic endpoint

**Files:**
- Create or modify: `app/epistemic.py`
- Modify: `app/main.py` or the existing route registration module
- Test: `tests/test_epistemic.py`

**Interfaces:**
- `POST /epistemic/review`
- Request fields: `candidate_id`, `claims`, `evidence`
- Response fields: `candidate_id`, `decision`, `claims`, `can_pass=false`, `promotion_authority=NONE`, `execution_authority=NONE`

- [ ] Write endpoint tests for the 293-test claim becoming a corrected repository-scope claim.
- [ ] Run endpoint tests and confirm failure before route implementation.
- [ ] Implement deterministic scope rules for repository tests, runtime acceptance, deployment, and external dependencies.
- [ ] Run endpoint tests and confirm pass.
- [ ] Commit the endpoint.

### Task 3: Wire ROAD registry and EPISTEMIC gate

**Files:**
- Modify: `road-mcp/src/server.ts`
- Modify: `road-mcp/tests/test-evidence.test.mjs`

**Interfaces:**
- Registry includes `epistemic-claim-audit`.
- `certificationChecks()` makes EPISTEMIC PASS only from that record.

- [ ] Add failing gate tests for PASS, OVERSTATED/BLOCKED, missing, and wrong-SHA cases.
- [ ] Run them red.
- [ ] Add registry loading and gate wiring.
- [ ] Run the full ROAD test/build suite.
- [ ] Commit the gate wiring.

### Task 4: Configure deployment and verify production

**Files:**
- Modify: `.github/workflows/railway-production-activate.yml` if route changes require SARA deployment coverage
- Modify: `.github/workflows/road-mcp-railway-deploy.yml` if ROAD source changes require deploy coverage
- Modify: `tests/test_road_mcp_deployment_trigger.py`

- [ ] Add the live Epistemic URL to ROAD service configuration.
- [ ] Push the implementation to `main`.
- [ ] Verify GitHub validation and both Railway deployments.
- [ ] Query live SARA Epistemic review and live ROAD `get_gate_evidence`/`run_certification_check`.
- [ ] Confirm EPISTEMIC is PASS only when its claim ledger is exact-SHA-bound and all release claims are properly scoped.
- [ ] Commit or document any deployment-only configuration separately from source changes.
