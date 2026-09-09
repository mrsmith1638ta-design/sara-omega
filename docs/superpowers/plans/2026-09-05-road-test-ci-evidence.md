# ROAD Exact-SHA TEST/CI Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ROAD's TEST gate evidence-driven and exact-source-bound, using SARA's live production self-test predicates plus the successful GitHub Actions validation run for the exact deployed commit SHA.

**Architecture:** SARA production publishes a validated `source_commit_sha` in its existing production-acceptance evidence. ROAD is source-controlled under `road-mcp/`, parses the runtime SHA/self-test predicates, queries the canonical GitHub Actions workflow for that exact SHA, validates the canonical `validate` job and required steps, creates a `test-ci-validation` evidence record, and allows TEST=PASS only from that record. Missing, ambiguous, stale, mismatched, inaccessible, or failed evidence stays UNVERIFIED.

**Tech Stack:** Python 3.11+/FastAPI/pytest; TypeScript 5/Node 20+/MCP SDK/Zod/node:test; GitHub Actions REST API; Railway.

**Spec:** `docs/superpowers/specs/2026-09-05-road-test-ci-evidence-design.md`

## Global Constraints

- Never infer a deployed SHA from branch name, release version, latest `main`, or a user assertion.
- Never convert a failed/missing/inaccessible CI state to PASS.
- Never use a GitHub run for a SHA other than the live deployed `source_commit_sha`.
- Preserve existing Context.dev and production-acceptance behavior.
- Do not promote unrelated ROAD gates as part of this repair.
- Do not merge or deploy OAuth/Perplexity PR #11.
- Do not commit credentials, Railway tokens, GitHub tokens, vendor secrets, or private email content.
- Production deployment happens only after branch CI is green and exact-source evidence is verified.

---

### Task 1: Canonicalize the current ROAD snapshot under source control

**Files:**
- Create: `road-mcp/src/server.ts`
- Create: `road-mcp/data/roadmap.md`
- Create: `road-mcp/package.json`
- Create: `road-mcp/package-lock.json`
- Create: `road-mcp/tsconfig.json`
- Create: `road-mcp/railway.json`
- Create: `road-mcp/README.md`

- [ ] Retrieve the exact deployed files from Railway service `9d5b1dc9-aa3a-433d-b31e-7f9d77957b12` and record their SHA-256 hashes before editing.
- [ ] Commit the exact snapshot to `road-mcp/` with no behavioral edits.
- [ ] Verify `cd road-mcp && npm ci && npm run check && npm run build` succeeds and the generated server preserves all 11 current ROAD tools.
- [ ] Compare source hashes/content with the deployed snapshot and document intentional differences only if Railway metadata normalization is required.

### Task 2: RED — require exact production source SHA in SARA acceptance evidence

**Files:**
- Modify: `tests/test_production_bootstrap.py`
- Later modify: `sara_production_bootstrap.py`

- [ ] Add `test_preflight_exposes_valid_source_commit_sha` that sets `SARA_SOURCE_COMMIT_SHA` to a 40-hex SHA and asserts `run_preflight()` returns it.
- [ ] Add `test_preflight_omits_invalid_source_commit_sha` covering missing and malformed values.
- [ ] Run `pytest -q tests/test_production_bootstrap.py` and confirm the new positive test fails because `source_commit_sha` is absent.
- [ ] Commit the RED regression separately.

### Task 3: GREEN — add fail-closed SARA source-SHA attestation

**Files:**
- Modify: `sara_production_bootstrap.py`
- Modify: `tests/test_production_bootstrap.py` only if a test correction, not expectation weakening, is required.

- [ ] Add a helper that accepts only `^[0-9a-fA-F]{40}$` and normalizes to lowercase.
- [ ] Read only `SARA_SOURCE_COMMIT_SHA`; never derive from GitHub or release version.
- [ ] Add valid `source_commit_sha` to `run_preflight()` evidence and the public `/health/production-acceptance` whitelist.
- [ ] Ensure missing/malformed SHA does not make `production_accepted` false by itself but produces no verified SHA for ROAD TEST, preserving separation of ACCEPTANCE and TEST.
- [ ] Run `pytest -q tests/test_production_bootstrap.py` until green.
- [ ] Run the full Python suite to ensure the acceptance controller is unchanged apart from source provenance.

### Task 4: RED — add ROAD TEST evidence regression suite

**Files:**
- Create: `road-mcp/tests/test-evidence.test.mjs`
- Modify: `road-mcp/package.json` only to add `test` script if absent.
- Later modify: `road-mcp/src/server.ts` or an extracted focused module.

- [ ] Add a positive contract expecting `test-ci-validation` PASS from exact-SHA successful workflow/job/steps plus runtime `checkpoint_self_test=true`, `bootstrap_ready=true`, `chain_valid=true`.
- [ ] Add negative contracts for missing SHA, malformed SHA, one-character SHA mismatch, workflow mismatch, failed/incomplete workflow, missing/failed validate job, every required-step failure/missing state, false runtime predicates, GitHub fetch failure, malformed payload, oversized payload, and ambiguous multiple valid runs.
- [ ] Add a TEST gate contract asserting `evidenceIds` is exactly `["test-ci-validation"]` and status is UNVERIFIED when the evidence record is not PASS.
- [ ] Run `cd road-mcp && npm test` and confirm RED failures are caused by the missing TEST evidence implementation, not test syntax.
- [ ] Commit RED separately.

### Task 5: GREEN — implement GitHub exact-SHA TEST evidence loader

**Files:**
- Modify: `road-mcp/src/server.ts`
- Optionally create: `road-mcp/src/testEvidence.ts` if extraction keeps the unit isolated and testable.
- Modify: `road-mcp/tests/test-evidence.test.mjs`

- [ ] Extend runtime-attestation parsing to carry `sourceCommitSha`, `checkpointSelfTest`, `bootstrapReady`, and `chainValid` without changing ACCEPTANCE logic.
- [ ] Add a bounded GitHub JSON fetcher with 4.5-second timeout, 128 KB payload cap, canonical host/path allowlist, GitHub API version header, and no credential requirement.
- [ ] Query canonical workflow runs at `.github/workflows/sara-v32-validate.yml` filtered by exact `head_sha` and completed status.
- [ ] Require exactly one unambiguous successful canonical run for the exact source SHA.
- [ ] Query that run's jobs; require canonical `validate` job success and all six approved step names success.
- [ ] Build a bounded, hashable evidence summary and emit `test-ci-validation` with PASS only if every predicate passes; otherwise UNVERIFIED.
- [ ] Add explicit TEST branch in `certificationChecks()` referencing only `test-ci-validation`.
- [ ] Run `npm test`, `npm run check`, and `npm run build` until green.

### Task 6: Add ROAD validation to the canonical SARA workflow

**Files:**
- Modify: `.github/workflows/sara-v32-validate.yml`

- [ ] Add a named `ROAD MCP validation` step that runs `npm ci`, `npm test`, `npm run check`, and `npm run build` from `road-mcp/`.
- [ ] Do not rename the six SARA TEST evidence step names, because ROAD verifies those exact names.
- [ ] Do not weaken existing Python tests, adversarial gate, shell checks, Windows syntax gate, or Docker build.
- [ ] Validate the workflow syntax and run the branch workflow.

### Task 7: PR verification and merge

**Files:**
- Review all changed files.

- [ ] Open a draft PR from `feature/road-test-evidence-binding` to `main` with RED/GREEN evidence and exact hashes.
- [ ] Require branch validation success.
- [ ] Inspect the PR diff for secrets and unrelated OAuth/Perplexity changes.
- [ ] Run/confirm full pytest, ROAD node:test, TypeScript check/build, adversarial 5/5, and Docker build.
- [ ] Verify `main` has not moved unexpectedly; merge only the tested exact head.
- [ ] Record resulting merge SHA and the successful `SARA-OMEGA V3.2.1 validation` run bound to that SHA.

### Task 8: Exact production deployment and ROAD promotion

**SARA Railway production:** existing live SARA service only.

**ROAD Railway production:** project `495f4e9d-1f63-4511-8a02-a971452e9170`, environment `a726e05d-da03-4af7-9eee-657e17e36770`, service `9d5b1dc9-aa3a-433d-b31e-7f9d77957b12`.

- [ ] Set `SARA_SOURCE_COMMIT_SHA` on the existing SARA production service to the exact merged/promoted SHA; do not expose the value as authority until the matching source is deployed.
- [ ] Deploy SARA from that exact merged SHA, preserving its existing `/data` volume and variables.
- [ ] Verify live `/health/production-acceptance` still has `production_accepted=true`, runtime self-test predicates true, and `source_commit_sha` exactly equals the deployed commit.
- [ ] Deploy `road-mcp/` to the existing ROAD service from the exact source-controlled tree, preserving `ROAD_RAILWAY_ATTESTATION_URL` and `ROAD_CONTEXTDEV_RESOLVER_URL`.
- [ ] Verify ROAD MCP initialize/tools/list remains healthy and all 11 tools remain exposed.
- [ ] Call `get_gate_evidence` for `test-ci-validation`; require PASS with the exact deployed SHA and successful GitHub run evidence.
- [ ] Call `run_certification_check`; require TEST=PASS and `evidenceIds=["test-ci-validation"]` while unrelated incomplete gates remain fail-closed.
- [ ] Re-check Context.dev authorization PASS and production ACCEPTANCE PASS.
- [ ] Do not sign/release until independent downstream gates have their own verified evidence.

### Task 9: Final evidence record

**Files:**
- Update PR #11 release note only with live evidence after successful deployment.

- [ ] Record exact SARA merge SHA, SARA Railway deployment ID, CI run/job IDs, ROAD source commit/tree, ROAD deployment ID, `test-ci-validation` hash, and fresh ROAD gate states.
- [ ] State only gates actually returned PASS; do not infer downstream PASS from TEST.
