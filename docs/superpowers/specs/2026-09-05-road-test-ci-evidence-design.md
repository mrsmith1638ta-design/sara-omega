# ROAD Exact-SHA TEST/CI Evidence Design

## Objective

Move ROAD's `TEST` gate from a hard-coded `UNVERIFIED` state to an evidence-driven state without manufacturing PASS. ROAD must certify TEST only when the exact SARA-OMEGA source commit running in production is bound to a successful GitHub Actions validation run and the live production runtime independently reports its required self-test predicates.

## Current root cause

The live ROAD MCP service currently builds only three evidence records: `roadmap-source`, `production-attestation`, and `contextdev-authorization`. `certificationChecks()` has no TEST-specific branch, so TEST falls through to the default path and is always `UNVERIFIED` with `evidenceIds=["roadmap-source"]`.

SARA production already exposes useful runtime verification fields at `/health/production-acceptance`, including `checkpoint_self_test`, `bootstrap_ready`, `chain_valid`, `failsafe_configured`, `hardening_profile`, and `production_accepted`. ROAD currently ignores those fields for TEST.

GitHub Actions already provides commit-bound implementation evidence. For production commit `2c315616e8c12beeb7a7fa41ed3834c40f223920`, validation run `33987874494` completed successfully. Its `validate` job completed successfully and the required compile, shell sanitation, native Windows syntax, full pytest/production bootstrap test, focused adversarial, and Railway container-build steps all completed successfully.

## Canonical source control

The currently deployed ROAD service is a local Railway snapshot rather than repository-linked source. To prevent this repair from becoming a one-off container mutation, the ROAD source is canonicalized under the existing SARA repository at `road-mcp/`.

The canonical ROAD source package contains:

- `road-mcp/src/server.ts` — MCP server, evidence loaders, certification checks, defensive suite, and Action compatibility bridge.
- `road-mcp/data/roadmap.md` — existing canonical ROAD completion roadmap.
- `road-mcp/package.json` and `road-mcp/package-lock.json` — Node dependency contract.
- `road-mcp/tsconfig.json` — TypeScript compiler contract.
- `road-mcp/railway.json` — Railway build/start/health configuration.
- `road-mcp/README.md` — service operation and evidence contract.
- `road-mcp/tests/test-evidence.test.mjs` — regression tests for exact-SHA TEST evidence and fail-closed negative cases.

No ROAD secret, token, or private authorization evidence is committed.

## SARA production attestation contract

`sara_production_bootstrap.py` adds `source_commit_sha` to production acceptance evidence. The value comes only from `SARA_SOURCE_COMMIT_SHA`.

Requirements:

- `source_commit_sha` must be a lowercase or uppercase 40-character hexadecimal Git SHA.
- If missing or malformed, the public acceptance endpoint reports no verified source commit and ROAD TEST remains `UNVERIFIED`.
- The deployment process must set `SARA_SOURCE_COMMIT_SHA` to the exact commit being promoted. ROAD may not infer it from branch name, release version, current GitHub `main`, or user assertion.
- The existing acceptance predicate remains unchanged; adding source SHA does not weaken `production_accepted`.

## GitHub CI evidence contract

ROAD adds a live GitHub evidence loader hard-bound to:

- repository: `mrsmith1638ta-design/sara-omega`
- workflow path: `.github/workflows/sara-v32-validate.yml`
- workflow name: `SARA-OMEGA V3.2.1 validation`
- job name: `validate`

The loader consumes the exact `source_commit_sha` from live production attestation and queries GitHub Actions for runs with that head SHA. It accepts only a completed `success` run for the canonical workflow. It then verifies the `validate` job is completed successfully and verifies these required job steps are completed successfully:

1. `Compile`
2. `Deployment shell sanitation`
3. `Native Windows activator syntax`
4. `Production bootstrap tests`
5. `Focused adversarial gate`
6. `Railway container build`

ROAD does not accept a run for another SHA, another repository, another workflow, another job, a cancelled/skipped/in-progress run, or a run missing any required step.

GitHub evidence is public metadata for the public SARA repository; no GitHub credential is required by this design. ROAD uses bounded HTTPS requests, a 4.5-second timeout per request, payload-size limits, sanitized returned URLs, and no query-string/token output.

## `test-ci-validation` evidence record

`buildEvidenceRegistry()` adds:

```text
id: test-ci-validation
subject: Exact-source SARA-OMEGA TEST/CI validation
status: PASS | UNVERIFIED
source: sanitized canonical GitHub Actions run URL or canonical GitHub API source
checkedAt: current timestamp
hash: SHA-256 over the bounded evidence summary
```

`PASS` requires all of the following simultaneously:

- live production attestation is reachable;
- `source_commit_sha` is a valid 40-hex SHA;
- `checkpoint_self_test == true`;
- `bootstrap_ready == true`;
- `chain_valid == true`;
- canonical GitHub validation workflow has a completed successful run whose `head_sha` exactly equals `source_commit_sha`;
- canonical `validate` job concluded `success`;
- all six required steps concluded `success`.

Any missing, false, stale, malformed, mismatched, inaccessible, or ambiguous condition returns `UNVERIFIED`. TEST evidence never returns PASS from roadmap completion, release version, branch name, manually supplied passed-gate claims, or production acceptance alone.

## TEST gate behavior

`certificationChecks()` adds an explicit TEST branch:

- TEST `PASS` only when `test-ci-validation.status == PASS`.
- Otherwise TEST `UNVERIFIED`.
- TEST `evidenceIds` becomes exactly `["test-ci-validation"]`.
- TEST failure continues to enter `upstreamFailures`, preserving existing downstream fail-closed behavior.

This repair does not automatically promote BUILD, SECURITY, ADVERSARIAL, EPISTEMIC, GOVERNANCE, PRIVACY, PERFORMANCE, RECOVERY, MULTI-CLOUD, SIGN, or RELEASE. Each remains governed by its own evidence path.

## Candidate binding

The existing `verify_release_candidate` schema does not accept a candidate commit SHA. This repair does not falsely claim exact-candidate release certification. The TEST evidence record is bound to the exact deployed production SHA, while release-candidate SHA binding remains a separate future ROAD hardening item.

## Adversarial requirements

Regression tests must prove ROAD returns TEST `UNVERIFIED` when any of these occur:

- no `SARA_SOURCE_COMMIT_SHA` / no `source_commit_sha`;
- malformed SHA;
- GitHub run SHA differs by one character;
- workflow name/path mismatch;
- workflow conclusion is failure/cancelled/skipped/in-progress;
- `validate` job missing or failed;
- any one required step missing, skipped, cancelled, or failed;
- runtime `checkpoint_self_test=false`;
- runtime `bootstrap_ready=false`;
- runtime `chain_valid=false`;
- GitHub API unavailable or returns malformed/oversized evidence;
- duplicate successful runs include no uniquely valid canonical run.

A positive test proves the exact-SHA successful run plus all live runtime predicates yields TEST `PASS` with `evidenceIds=["test-ci-validation"]`.

## Deployment acceptance

Before production promotion:

1. ROAD source-control snapshot must compile from `road-mcp/`.
2. RED regression must fail against the pre-fix ROAD behavior for the intended reason.
3. GREEN regression and all ROAD tests must pass.
4. SARA's existing Python validation suite must remain green after adding `source_commit_sha`.
5. GitHub Actions must complete successfully for the exact merge commit.
6. `SARA_SOURCE_COMMIT_SHA` must equal the exact promoted commit SHA.
7. Existing live SARA production acceptance must remain PASS.
8. Existing Context.dev authorization must remain PASS.
9. Live ROAD `get_gate_evidence("test-ci-validation")` must return PASS.
10. Live ROAD `run_certification_check` must report TEST=PASS and must still refuse to manufacture PASS for unrelated incomplete gates.

No OAuth/Perplexity feature branch is merged or deployed as part of this repair.