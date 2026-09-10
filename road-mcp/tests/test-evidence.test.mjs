// RED/GREEN regression suite for the `test-ci-validation` evidence record and
// the ROAD TEST gate, per docs/superpowers/specs/2026-09-05-road-test-ci-evidence-design.md
// "Adversarial requirements" and "TEST gate behavior" sections.
//
// This suite is intentionally network-free: it drives `computeTestCiEvidence`
// / `buildTestCiValidationEvidence` with fully synthetic runtime-attestation
// and GitHub-fetch stubs, and drives `certificationChecks` with a synthetic
// evidence-record list. No live HTTP calls are made.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  computeTestCiEvidence,
  buildTestCiValidationEvidence,
  parseProductionRuntimeAttestation,
  normalizeSourceCommitSha,
  TEST_CI_EVIDENCE_ID,
  CANONICAL_WORKFLOW_NAME,
  CANONICAL_WORKFLOW_PATH,
  CANONICAL_JOB_NAME,
  REQUIRED_STEP_NAMES,
} from "../dist/testEvidence.js";
import {
  MADHOUSE_ADVERSARIAL_EVIDENCE_ID,
  buildMadhouseAdversarialEvidence,
  computeMadhouseAdversarialEvidence,
} from "../dist/madhouseEvidence.js";
import {
  EPISTEMIC_EVIDENCE_ID,
  buildEpistemicEvidence,
  computeEpistemicEvidence,
} from "../dist/epistemicEvidence.js";
import { certificationChecks, createApp } from "../dist/server.js";
import { buildRoadGateEvidence, ROAD_GATE_EVIDENCE_IDS } from "../dist/roadGateEvidence.js";

const VALID_SHA = "a".repeat(40);
const OTHER_SHA = "b".repeat(40);
const BLOCKING_SHA = "c".repeat(40);

function attestation(overrides = {}) {
  return {
    reachable: true,
    sourceCommitSha: VALID_SHA,
    checkpointSelfTest: true,
    bootstrapReady: true,
    chainValid: true,
    productionAccepted: true,
    ...overrides,
  };
}

function stepList(overrides = {}) {
  return REQUIRED_STEP_NAMES.map((name) => ({
    name,
    status: overrides[name]?.status ?? "completed",
    conclusion: overrides[name]?.conclusion ?? "success",
  }));
}

function successfulRun(overrides = {}) {
  return {
    id: 1001,
    head_sha: VALID_SHA,
    status: "completed",
    conclusion: "success",
    name: CANONICAL_WORKFLOW_NAME,
    path: CANONICAL_WORKFLOW_PATH,
    html_url: "https://github.com/mrsmith1638ta-design/sara-omega/actions/runs/1001?extra=token123",
    ...overrides,
  };
}

/** Builds a githubGet fetcher from explicit runs/jobs responses (or errors). */
function makeGithubGet({ runs, runsError, jobs, jobsError } = {}) {
  return async (path) => {
    if (path.includes("/actions/runs/")) {
      if (jobsError) return { ok: false, error: jobsError, url: "https://api.github.com" + path };
      return { ok: true, status: 200, json: { jobs: jobs ?? [] }, url: "https://api.github.com" + path };
    }
    if (runsError) return { ok: false, error: runsError, url: "https://api.github.com" + path };
    return { ok: true, status: 200, json: { workflow_runs: runs ?? [] }, url: "https://api.github.com" + path };
  };
}

function validateJob(overrides = {}) {
  return {
    name: CANONICAL_JOB_NAME,
    status: "completed",
    conclusion: "success",
    steps: stepList(),
    ...overrides,
  };
}

function epistemicReview(overrides = {}) {
  return {
    service: "sara-epistemic-agent",
    candidate_id: VALID_SHA,
    decision: "READY_FOR_VERIFICATION",
    can_pass: false,
    promotion_authority: "NONE",
    execution_authority: "NONE",
    claims: [{ state: "SUPPORTED" }],
    ...overrides,
  };
}

function makeEpistemicFetch(overrides = {}) {
  const review = epistemicReview(overrides);
  return async () => ({ ok: true, status: 200, json: review, url: "https://example.test/epistemic/review" });
}

function madhouseHealth(overrides = {}) {
  return {
    status: "ok",
    service: "sara-madhouse-agent",
    can_block: true,
    can_pass: false,
    promotion_authority: "NONE",
    boundary: "may_block_candidates; never certifies production PASS",
    ...overrides,
  };
}

function madhouseReview(overrides = {}) {
  return {
    service: "sara-madhouse-agent",
    candidate_id: VALID_SHA,
    decision: "READY_FOR_VERIFICATION",
    can_block: true,
    can_pass: false,
    promotion_authority: "NONE",
    execution_authority: "NONE",
    findings: [],
    evidence_ledger: [],
    failure_fingerprints: [],
    required_validation: ["compile", "unit_tests", "security_review"],
    boundary: "Madhouse absence of findings is not proof of correctness; send survivors to Verification/ROAD/SIOS.",
    ...overrides,
  };
}

function makeMadhouseFetch({ health, healthError, review, reviewError } = {}) {
  return async (url, init) => {
    if (init?.method === "POST") {
      if (reviewError) return { ok: false, error: reviewError, url };
      return { ok: true, status: 200, json: review ?? madhouseReview(), url };
    }
    if (healthError) return { ok: false, error: healthError, url };
    return { ok: true, status: 200, json: health ?? madhouseHealth(), url };
  };
}

// ---------------------------------------------------------------------------
// Positive contract
// ---------------------------------------------------------------------------

test("PASS: exact-SHA successful run + successful validate job + all steps + true runtime predicates", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob()] });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "PASS");
  assert.equal(summary.sourceCommitSha, VALID_SHA);
  assert.equal(summary.requiredStepsSatisfied, true);
});

test("PASS: buildTestCiValidationEvidence produces id=test-ci-validation with sanitized source URL", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob()] });
  const record = await buildTestCiValidationEvidence(async () => attestation(), githubGet);
  assert.equal(record.id, TEST_CI_EVIDENCE_ID);
  assert.equal(record.status, "PASS");
  assert.equal(record.evidenceState, "VERIFIED");
  assert.ok(!record.source.includes("token123"), "source URL must not leak query strings/tokens");
  assert.ok(!record.source.includes("?"), "source URL must be sanitized of query strings");
  assert.match(record.hash, /^[0-9a-f]{64}$/);
});

test("PASS: Madhouse adversarial evidence binds health + review artifact to exact deployed SHA", async () => {
  const fetcher = makeMadhouseFetch();
  const summary = await computeMadhouseAdversarialEvidence(attestation(), fetcher);
  assert.equal(summary.status, "PASS");
  assert.equal(summary.sourceCommitSha, VALID_SHA);
  assert.equal(summary.health.canBlock, true);
  assert.equal(summary.health.canPass, false);
  assert.equal(summary.health.promotionAuthority, "NONE");
  assert.equal(summary.review.candidateId, VALID_SHA);
  assert.equal(summary.review.decision, "READY_FOR_VERIFICATION");
  assert.equal(summary.review.canPass, false);
  assert.equal(summary.review.promotionAuthority, "NONE");
  assert.equal(summary.review.executionAuthority, "NONE");
});

test("PASS: buildMadhouseAdversarialEvidence produces a verified ROAD evidence artifact", async () => {
  const record = await buildMadhouseAdversarialEvidence(async () => attestation(), makeMadhouseFetch());
  assert.equal(record.id, MADHOUSE_ADVERSARIAL_EVIDENCE_ID);
  assert.equal(record.status, "PASS");
  assert.equal(record.evidenceState, "VERIFIED");
  assert.ok(record.detail.includes(VALID_SHA));
  assert.match(record.hash, /^[0-9a-f]{64}$/);
});

test("PASS: ROAD MCP exposes GET /health for Railway healthchecks", async (t) => {
  const app = createApp();
  const server = app.listen(0);
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const address = server.address();
  assert.ok(address && typeof address === "object");

  const response = await fetch(`http://127.0.0.1:${address.port}/health`);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.status, "ok");
  assert.equal(body.service, "sara-omega-road-mcp");
});

test("BLOCKED: Madhouse BLOCKED review blocks the adversarial evidence record", async () => {
  const fetcher = makeMadhouseFetch({
    review: madhouseReview({
      candidate_id: BLOCKING_SHA,
      decision: "BLOCKED",
      findings: [{ class: "SYNTAX", severity: "BLOCKING" }],
      evidence_ledger: [{ issue: "SYNTAX", severity: "BLOCKING" }],
      failure_fingerprints: ["SYNTAX:parser-failure"],
    }),
  });
  const summary = await computeMadhouseAdversarialEvidence(attestation({ sourceCommitSha: BLOCKING_SHA }), fetcher);
  assert.equal(summary.status, "BLOCKED");
  assert.match(summary.reason, /madhouse_review_blocked/);
  assert.equal(summary.review.decision, "BLOCKED");
});

test("UNVERIFIED: Madhouse health cannot claim promotion authority or PASS authority", async () => {
  const fetcher = makeMadhouseFetch({ health: madhouseHealth({ can_pass: true, promotion_authority: "PASS" }) });
  const summary = await computeMadhouseAdversarialEvidence(attestation(), fetcher);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /madhouse_health_authority_boundary_failed/);
});

test("UNVERIFIED: Madhouse review artifact must match exact deployed SHA", async () => {
  const fetcher = makeMadhouseFetch({ review: madhouseReview({ candidate_id: OTHER_SHA }) });
  const summary = await computeMadhouseAdversarialEvidence(attestation(), fetcher);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /madhouse_review_sha_mismatch/);
});

// ---------------------------------------------------------------------------
// Negative contracts (design spec "Adversarial requirements")
// ---------------------------------------------------------------------------

test("UNVERIFIED: no SARA_SOURCE_COMMIT_SHA / no source_commit_sha", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob()] });
  const summary = await computeTestCiEvidence(attestation({ sourceCommitSha: null }), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /missing_or_malformed_source_commit_sha/);
});

test("UNVERIFIED: malformed SHA is rejected by normalizeSourceCommitSha", () => {
  assert.equal(normalizeSourceCommitSha("not-a-sha"), null);
  assert.equal(normalizeSourceCommitSha("a".repeat(39)), null);
  assert.equal(normalizeSourceCommitSha("g".repeat(40)), null);
  assert.equal(normalizeSourceCommitSha(VALID_SHA.toUpperCase()), VALID_SHA);
});

test("UNVERIFIED: GitHub run SHA differs by one character from deployed SHA", async () => {
  const almostSha = VALID_SHA.slice(0, -1) + "c";
  const githubGet = makeGithubGet({ runs: [successfulRun({ head_sha: almostSha })], jobs: [validateJob()] });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /no_matching_successful_canonical_run/);
});

test("UNVERIFIED: workflow name mismatch", async () => {
  const githubGet = makeGithubGet({
    runs: [successfulRun({ name: "Some other workflow" })],
    jobs: [validateJob()],
  });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /no_matching_successful_canonical_run/);
});

test("UNVERIFIED: workflow path mismatch", async () => {
  const githubGet = makeGithubGet({
    runs: [successfulRun({ path: ".github/workflows/other.yml" })],
    jobs: [validateJob()],
  });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
});

for (const conclusion of ["failure", "cancelled", "skipped"]) {
  test(`UNVERIFIED: workflow conclusion is ${conclusion}`, async () => {
    const githubGet = makeGithubGet({ runs: [successfulRun({ conclusion })], jobs: [validateJob()] });
    const summary = await computeTestCiEvidence(attestation(), githubGet);
    assert.equal(summary.status, "UNVERIFIED");
  });
}

test("UNVERIFIED: workflow run is in-progress (status != completed)", async () => {
  const githubGet = makeGithubGet({
    runs: [successfulRun({ status: "in_progress", conclusion: null })],
    jobs: [validateJob()],
  });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
});

test("UNVERIFIED: validate job missing from run", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [{ name: "other-job", status: "completed", conclusion: "success", steps: [] }] });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /validate_job_missing/);
});

test("UNVERIFIED: validate job failed", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob({ conclusion: "failure" })] });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /validate_job_not_successful/);
});

for (const requiredName of REQUIRED_STEP_NAMES) {
  test(`UNVERIFIED: required step "${requiredName}" missing`, async () => {
    const steps = stepList().filter((s) => s.name !== requiredName);
    const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob({ steps })] });
    const summary = await computeTestCiEvidence(attestation(), githubGet);
    assert.equal(summary.status, "UNVERIFIED");
    assert.match(summary.reason, new RegExp(`required_step_missing:${requiredName.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&")}`));
  });

  test(`UNVERIFIED: required step "${requiredName}" skipped/cancelled/failed`, async () => {
    for (const conclusion of ["skipped", "cancelled", "failure"]) {
      const steps = stepList({ [requiredName]: { conclusion } });
      const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob({ steps })] });
      const summary = await computeTestCiEvidence(attestation(), githubGet);
      assert.equal(summary.status, "UNVERIFIED", `expected UNVERIFIED for ${requiredName}=${conclusion}`);
      assert.match(summary.reason, /required_step_not_successful/);
    }
  });
}

test("UNVERIFIED: runtime checkpoint_self_test=false", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob()] });
  const summary = await computeTestCiEvidence(attestation({ checkpointSelfTest: false }), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /checkpoint_self_test_not_true/);
});

test("UNVERIFIED: runtime bootstrap_ready=false", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob()] });
  const summary = await computeTestCiEvidence(attestation({ bootstrapReady: false }), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /bootstrap_ready_not_true/);
});

test("UNVERIFIED: runtime chain_valid=false", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob()] });
  const summary = await computeTestCiEvidence(attestation({ chainValid: false }), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /chain_valid_not_true/);
});

test("UNVERIFIED: production attestation endpoint unreachable", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobs: [validateJob()] });
  const summary = await computeTestCiEvidence({ reachable: false, sourceCommitSha: null, checkpointSelfTest: null, bootstrapReady: null, chainValid: null, productionAccepted: null }, githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /production_attestation_unreachable/);
});

test("UNVERIFIED: GitHub API unavailable for workflow runs", async () => {
  const githubGet = makeGithubGet({ runsError: "fetch_failed:network_error" });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /github_runs_fetch_failed/);
});

test("UNVERIFIED: GitHub API unavailable for run jobs", async () => {
  const githubGet = makeGithubGet({ runs: [successfulRun()], jobsError: "http_503" });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /github_jobs_fetch_failed/);
});

test("UNVERIFIED: GitHub runs payload malformed (not an array)", async () => {
  const githubGet = async (path) =>
    path.includes("/actions/runs/")
      ? { ok: true, json: { jobs: [validateJob()] }, url: "x" }
      : { ok: true, json: { workflow_runs: "not-an-array" }, url: "x" };
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /github_runs_malformed_payload/);
});

test("UNVERIFIED: GitHub jobs payload malformed (not an array)", async () => {
  const githubGet = async (path) =>
    path.includes("/actions/runs/")
      ? { ok: true, json: { jobs: "nope" }, url: "x" }
      : { ok: true, json: { workflow_runs: [successfulRun()] }, url: "x" };
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /github_jobs_malformed_payload/);
});

test("UNVERIFIED: oversized/malformed GitHub payload surfaces as fetch error, never PASS", async () => {
  const githubGet = async () => ({ ok: false, error: "payload_too_large", url: "https://api.github.com/x" });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
});

test("UNVERIFIED: duplicate successful runs for the same exact SHA are ambiguous", async () => {
  const githubGet = makeGithubGet({
    runs: [successfulRun({ id: 1001 }), successfulRun({ id: 1002 })],
    jobs: [validateJob()],
  });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
  assert.match(summary.reason, /ambiguous_multiple_valid_canonical_runs/);
});

test("UNVERIFIED: run for a different SHA in the result set is not treated as canonical", async () => {
  const githubGet = makeGithubGet({
    runs: [successfulRun({ head_sha: OTHER_SHA })],
    jobs: [validateJob()],
  });
  const summary = await computeTestCiEvidence(attestation(), githubGet);
  assert.equal(summary.status, "UNVERIFIED");
});

test("parseProductionRuntimeAttestation fails closed on malformed payload shapes", () => {
  assert.equal(parseProductionRuntimeAttestation(null).reachable, false);
  assert.equal(parseProductionRuntimeAttestation("oops").reachable, false);
  assert.equal(parseProductionRuntimeAttestation([1, 2, 3]).reachable, false);
  const parsed = parseProductionRuntimeAttestation({ source_commit_sha: "bad", checkpoint_self_test: "yes" });
  assert.equal(parsed.reachable, true);
  assert.equal(parsed.sourceCommitSha, null);
  assert.equal(parsed.checkpointSelfTest, null);
});

// ---------------------------------------------------------------------------
// TEST gate contract in certificationChecks()
// ---------------------------------------------------------------------------

function baseRecords(overrides = {}) {
  return [
    {
      id: "roadmap-source",
      subject: "x",
      status: "PASS",
      evidenceState: "VERIFIED",
      source: "x",
      checkedAt: "2026-01-01T00:00:00.000Z",
      detail: "x",
      hash: "x",
    },
    {
      id: "production-attestation",
      subject: "x",
      status: "PASS",
      evidenceState: "VERIFIED",
      source: "x",
      checkedAt: "2026-01-01T00:00:00.000Z",
      detail: "x",
      hash: "x",
    },
    {
      id: "contextdev-authorization",
      subject: "x",
      status: "PASS",
      evidenceState: "VERIFIED",
      source: "x",
      checkedAt: "2026-01-01T00:00:00.000Z",
      detail: "x",
      hash: "x",
    },
    {
      id: TEST_CI_EVIDENCE_ID,
      subject: "Exact-source SARA-OMEGA TEST/CI validation",
      status: "UNVERIFIED",
      evidenceState: "UNVERIFIED",
      source: "x",
      checkedAt: "2026-01-01T00:00:00.000Z",
      detail: "x",
      hash: "x",
      ...overrides,
    },
  ];
}

function baseRecordsWithMadhouse(testOverrides = {}, madhouseOverrides = {}) {
  return [
    ...baseRecords(testOverrides),
    {
      id: MADHOUSE_ADVERSARIAL_EVIDENCE_ID,
      subject: "SARA-OMEGA Madhouse adversarial review",
      status: "UNVERIFIED",
      evidenceState: "UNVERIFIED",
      source: "x",
      checkedAt: "2026-01-01T00:00:00.000Z",
      detail: "x",
      hash: "x",
      ...madhouseOverrides,
    },
  ];
}

function baseRecordsWithEpistemic(testOverrides = {}, madhouseOverrides = {}, epistemicOverrides = {}) {
  return [
    ...baseRecordsWithMadhouse(testOverrides, madhouseOverrides),
    {
      id: EPISTEMIC_EVIDENCE_ID,
      subject: "SARA-OMEGA Epistemic claim audit",
      status: "UNVERIFIED",
      evidenceState: "UNVERIFIED",
      source: "x",
      checkedAt: "2026-01-01T00:00:00.000Z",
      detail: "x",
      hash: "x",
      ...epistemicOverrides,
    },
  ];
}

test("Epistemic evidence passes only for exact-SHA scope-consistent claims", async () => {
  const summary = await computeEpistemicEvidence(
    attestation(),
    "293 repository tests passed in validation run 123.",
    makeEpistemicFetch()
  );
  assert.equal(summary.status, "PASS");
  assert.equal(summary.sourceCommitSha, VALID_SHA);
});

test("Epistemic evidence blocks overstated claims", async () => {
  const summary = await computeEpistemicEvidence(
    attestation(),
    "293 repository tests passed in validation run 123.",
    makeEpistemicFetch({
      decision: "BLOCKED",
      claims: [{ state: "OVERSTATED" }],
      can_pass: false,
      promotion_authority: "NONE",
      execution_authority: "NONE",
    })
  );
  assert.equal(summary.status, "BLOCKED");
});

test("Epistemic evidence rejects authority boundary violations and SHA mismatches", async () => {
  const authority = await computeEpistemicEvidence(
    attestation(),
    "293 repository tests passed in validation run 123.",
    makeEpistemicFetch({ can_pass: true })
  );
  assert.equal(authority.status, "UNVERIFIED");
  const mismatch = await computeEpistemicEvidence(
    attestation(),
    "293 repository tests passed in validation run 123.",
    makeEpistemicFetch({ candidate_id: OTHER_SHA })
  );
  assert.equal(mismatch.status, "UNVERIFIED");
});

test("buildEpistemicEvidence produces the ROAD evidence record", async () => {
  const record = await buildEpistemicEvidence(
    async () => attestation(),
    "293 repository tests passed in validation run 123.",
    makeEpistemicFetch(),
    () => new Date("2026-01-01T00:00:00.000Z")
  );
  assert.equal(record.id, EPISTEMIC_EVIDENCE_ID);
  assert.equal(record.status, "PASS");
  assert.equal(record.evidenceState, "VERIFIED");
  assert.match(record.detail, new RegExp(VALID_SHA));
});

test("TEST gate is PASS only when test-ci-validation evidence is PASS, with evidenceIds=[test-ci-validation]", () => {
  const records = baseRecords({ status: "PASS", evidenceState: "VERIFIED" });
  const checks = certificationChecks(records);
  const testCheck = checks.find((c) => c.gate === "TEST");
  assert.equal(testCheck.status, "PASS");
  assert.deepEqual(testCheck.evidenceIds, [TEST_CI_EVIDENCE_ID]);
});

test("TEST gate is UNVERIFIED when test-ci-validation evidence is UNVERIFIED, with evidenceIds=[test-ci-validation]", () => {
  const records = baseRecords({ status: "UNVERIFIED", evidenceState: "UNVERIFIED" });
  const checks = certificationChecks(records);
  const testCheck = checks.find((c) => c.gate === "TEST");
  assert.equal(testCheck.status, "UNVERIFIED");
  assert.deepEqual(testCheck.evidenceIds, [TEST_CI_EVIDENCE_ID]);
});

test("TEST gate is UNVERIFIED (never PASS) when test-ci-validation evidence record is entirely absent", () => {
  const records = baseRecords({ status: "UNVERIFIED" }).filter((r) => r.id !== TEST_CI_EVIDENCE_ID);
  const checks = certificationChecks(records);
  const testCheck = checks.find((c) => c.gate === "TEST");
  assert.equal(testCheck.status, "UNVERIFIED");
  assert.deepEqual(testCheck.evidenceIds, [TEST_CI_EVIDENCE_ID]);
});

test("TEST failure enters upstreamFailures for downstream gates (fail-closed propagation preserved)", () => {
  const records = baseRecords({ status: "UNVERIFIED" });
  const checks = certificationChecks(records);
  const securityCheck = checks.find((c) => c.gate === "SECURITY");
  assert.ok(securityCheck.preventedByUpstream.includes("TEST"));
});

test("TEST=PASS never manufactured from roadmap completion, release version, or other PASS evidence alone", () => {
  // All other evidence PASS, but test-ci-validation itself UNVERIFIED: TEST must stay UNVERIFIED.
  const records = baseRecords({ status: "UNVERIFIED" });
  const checks = certificationChecks(records);
  const testCheck = checks.find((c) => c.gate === "TEST");
  assert.notEqual(testCheck.status, "PASS");
});

test("ADVERSARIAL gate is PASS only from madhouse-adversarial-review evidence", () => {
  const records = baseRecordsWithMadhouse(
    { status: "PASS", evidenceState: "VERIFIED" },
    { status: "PASS", evidenceState: "VERIFIED" }
  );
  const checks = certificationChecks(records);
  const adversarialCheck = checks.find((c) => c.gate === "ADVERSARIAL");
  assert.equal(adversarialCheck.status, "PASS");
  assert.deepEqual(adversarialCheck.evidenceIds, [MADHOUSE_ADVERSARIAL_EVIDENCE_ID]);
});

test("ADVERSARIAL gate is UNVERIFIED when Madhouse evidence is absent", () => {
  const checks = certificationChecks(baseRecords({ status: "PASS", evidenceState: "VERIFIED" }));
  const adversarialCheck = checks.find((c) => c.gate === "ADVERSARIAL");
  assert.equal(adversarialCheck.status, "UNVERIFIED");
  assert.deepEqual(adversarialCheck.evidenceIds, [MADHOUSE_ADVERSARIAL_EVIDENCE_ID]);
});

test("ADVERSARIAL gate is BLOCKED when Madhouse evidence reports BLOCKED", () => {
  const records = baseRecordsWithMadhouse(
    { status: "PASS", evidenceState: "VERIFIED" },
    { status: "BLOCKED", evidenceState: "VERIFIED" }
  );
  const checks = certificationChecks(records);
  const adversarialCheck = checks.find((c) => c.gate === "ADVERSARIAL");
  assert.equal(adversarialCheck.status, "BLOCKED");
  assert.deepEqual(adversarialCheck.evidenceIds, [MADHOUSE_ADVERSARIAL_EVIDENCE_ID]);
});

test("EPISTEMIC gate is PASS only from epistemic-claim-audit evidence", () => {
  const checks = certificationChecks(baseRecordsWithEpistemic(
    { status: "PASS", evidenceState: "VERIFIED" },
    { status: "PASS", evidenceState: "VERIFIED" },
    { status: "PASS", evidenceState: "VERIFIED" }
  ));
  const check = checks.find((c) => c.gate === "EPISTEMIC");
  assert.equal(check.status, "PASS");
  assert.deepEqual(check.evidenceIds, [EPISTEMIC_EVIDENCE_ID]);
});

test("EPISTEMIC gate is BLOCKED when claim audit reports an overstatement", () => {
  const checks = certificationChecks(baseRecordsWithEpistemic(
    { status: "PASS", evidenceState: "VERIFIED" },
    { status: "PASS", evidenceState: "VERIFIED" },
    { status: "BLOCKED", evidenceState: "VERIFIED", detail: "claim is OVERSTATED" }
  ));
  const check = checks.find((c) => c.gate === "EPISTEMIC");
  assert.equal(check.status, "BLOCKED");
  assert.deepEqual(check.evidenceIds, [EPISTEMIC_EVIDENCE_ID]);
});

test("EPISTEMIC gate stays UNVERIFIED when the claim audit is absent", () => {
  const checks = certificationChecks(baseRecordsWithMadhouse({ status: "PASS", evidenceState: "VERIFIED" }, { status: "PASS", evidenceState: "VERIFIED" }));
  const check = checks.find((c) => c.gate === "EPISTEMIC");
  assert.equal(check.status, "UNVERIFIED");
  assert.deepEqual(check.evidenceIds, [EPISTEMIC_EVIDENCE_ID]);
});

test("remaining ROAD gates consume exact-SHA gate evidence", async () => {
  const observations = [
    { id: "contextdev-authorization", status: "PASS", source: "context-dev", detail: "authorized" },
    { id: "madhouse-adversarial-review", status: "PASS", source: "madhouse", detail: "ready" },
    { id: "epistemic-claim-audit", status: "PASS", source: "epistemic", detail: "supported" },
    { id: "test-ci-validation", status: "PASS", source: "github", detail: "validated" },
    { id: "production-attestation", status: "PASS", source: "railway", detail: "accepted" },
  ];
  const records = await buildRoadGateEvidence(
    attestation(),
    observations,
    async () => ({
      ok: true,
      status: 200,
      url: "https://example.test/road/gates/review",
      json: {
        candidate_id: VALID_SHA,
        decision: "READY_FOR_VERIFICATION",
        can_pass: false,
        promotion_authority: "NONE",
        execution_authority: "NONE",
        gates: [
          { gate: "GOVERNANCE", status: "PASS", detail: "governance" },
          { gate: "PRIVACY", status: "PASS", detail: "privacy" },
          { gate: "PERFORMANCE", status: "PASS", detail: "performance" },
          { gate: "RECOVERY", status: "PASS", detail: "recovery" },
          { gate: "MULTI-CLOUD", status: "PASS", detail: "multi-cloud" },
        ],
      },
    })
  );
  assert.deepEqual(records.map((record) => record.id), Object.values(ROAD_GATE_EVIDENCE_IDS));
  assert.ok(records.every((record) => record.status === "PASS" && record.evidenceState === "VERIFIED"));
});
