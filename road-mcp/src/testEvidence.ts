/**
 * test-ci-validation evidence loader.
 *
 * Implements the exact-SHA TEST/CI evidence contract from
 * docs/superpowers/specs/2026-09-05-road-test-ci-evidence-design.md.
 *
 * ROAD's TEST gate must never manufacture PASS. This module binds TEST
 * evidence to:
 *   1. the exact `source_commit_sha` reported by live SARA production
 *      attestation (never inferred from branch/version/main/user assertion);
 *   2. live runtime self-test predicates (`checkpoint_self_test`,
 *      `bootstrap_ready`, `chain_valid`);
 *   3. a single, unambiguous, completed-successful GitHub Actions run of the
 *      canonical `SARA-OMEGA V3.2.1 validation` workflow for that exact SHA,
 *      whose `validate` job completed successfully with all six required
 *      steps completed successfully.
 *
 * Any missing, malformed, mismatched, stale, ambiguous, or inaccessible
 * condition yields UNVERIFIED. This module performs only bounded,
 * unauthenticated, read-only HTTPS GET requests to the public GitHub REST
 * API. No GitHub token is read, required, or accepted.
 */

export const GITHUB_OWNER = "mrsmith1638ta-design";
export const GITHUB_REPO = "sara-omega";
export const CANONICAL_WORKFLOW_PATH = ".github/workflows/sara-v32-validate.yml";
export const CANONICAL_WORKFLOW_NAME = "SARA-OMEGA V3.2.1 validation";
export const CANONICAL_JOB_NAME = "validate";

export const REQUIRED_STEP_NAMES = [
  "Compile",
  "Deployment shell sanitation",
  "Native Windows activator syntax",
  "Production bootstrap tests",
  "Focused adversarial gate",
  "Railway container build",
] as const;

export const SOURCE_COMMIT_RE = /^[0-9a-fA-F]{40}$/;

const GITHUB_API_HOST = "api.github.com";
const GITHUB_API_VERSION = "2022-11-28";
const REQUEST_TIMEOUT_MS = 4500;
const MAX_PAYLOAD_BYTES = 128 * 1024;

export const TEST_CI_EVIDENCE_ID = "test-ci-validation";

export interface ProductionRuntimeAttestation {
  reachable: boolean;
  sourceCommitSha: string | null;
  checkpointSelfTest: boolean | null;
  bootstrapReady: boolean | null;
  chainValid: boolean | null;
  productionAccepted: boolean | null;
  raw?: unknown;
  error?: string;
}

export interface BoundedFetchResult {
  ok: boolean;
  status?: number;
  json?: unknown;
  error?: string;
  url: string;
}

export type Fetcher = (url: string) => Promise<BoundedFetchResult>;

/** Bounded, read-only, unauthenticated JSON GET with timeout and size cap. */
export async function boundedGithubGet(path: string): Promise<BoundedFetchResult> {
  const url = `https://${GITHUB_API_HOST}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: "GET",
      redirect: "error",
      signal: controller.signal,
      headers: {
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "sara-omega-road-mcp",
      },
    });
    const contentLengthHeader = res.headers.get("content-length");
    if (contentLengthHeader && Number(contentLengthHeader) > MAX_PAYLOAD_BYTES) {
      return { ok: false, error: "payload_too_large", url: sanitizeUrl(url) };
    }
    const text = await res.text();
    if (Buffer.byteLength(text, "utf8") > MAX_PAYLOAD_BYTES) {
      return { ok: false, error: "payload_too_large", url: sanitizeUrl(url) };
    }
    if (!res.ok) {
      return { ok: false, status: res.status, error: `http_${res.status}`, url: sanitizeUrl(url) };
    }
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      return { ok: false, error: "malformed_json", url: sanitizeUrl(url) };
    }
    return { ok: true, status: res.status, json, url: sanitizeUrl(url) };
  } catch (err) {
    const message = err instanceof Error ? err.message : "unknown_error";
    return { ok: false, error: `fetch_failed:${message}`, url: sanitizeUrl(url) };
  } finally {
    clearTimeout(timer);
  }
}

/** Never echo query strings or tokens back through ROAD output. */
export function sanitizeUrl(rawUrl: string): string {
  try {
    const parsed = new URL(rawUrl);
    parsed.search = "";
    parsed.hash = "";
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return "invalid-url";
  }
}

export function normalizeSourceCommitSha(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!SOURCE_COMMIT_RE.test(trimmed)) return null;
  return trimmed.toLowerCase();
}

/** Parses SARA's public /health/production-acceptance payload defensively. */
export function parseProductionRuntimeAttestation(raw: unknown): ProductionRuntimeAttestation {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return {
      reachable: false,
      sourceCommitSha: null,
      checkpointSelfTest: null,
      bootstrapReady: null,
      chainValid: null,
      productionAccepted: null,
      error: "malformed_attestation_payload",
    };
  }
  const obj = raw as Record<string, unknown>;
  const boolOrNull = (v: unknown): boolean | null => (typeof v === "boolean" ? v : null);
  return {
    reachable: true,
    sourceCommitSha: normalizeSourceCommitSha(obj["source_commit_sha"]),
    checkpointSelfTest: boolOrNull(obj["checkpoint_self_test"]),
    bootstrapReady: boolOrNull(obj["bootstrap_ready"]),
    chainValid: boolOrNull(obj["chain_valid"]),
    productionAccepted: boolOrNull(obj["production_accepted"]),
    raw: obj,
  };
}

interface WorkflowRun {
  id: number;
  head_sha?: unknown;
  status?: unknown;
  conclusion?: unknown;
  name?: unknown;
  path?: unknown;
  html_url?: unknown;
}

interface JobStep {
  name?: unknown;
  status?: unknown;
  conclusion?: unknown;
}

interface WorkflowJob {
  name?: unknown;
  status?: unknown;
  conclusion?: unknown;
  steps?: unknown;
}

export interface TestCiEvidenceSummary {
  status: "PASS" | "UNVERIFIED";
  reason: string;
  sourceCommitSha: string | null;
  runId: number | null;
  runUrl: string | null;
  runtime: {
    checkpointSelfTest: boolean | null;
    bootstrapReady: boolean | null;
    chainValid: boolean | null;
  };
  requiredStepsSatisfied: boolean;
}

export interface TestCiEvidenceRecord {
  id: typeof TEST_CI_EVIDENCE_ID;
  subject: string;
  status: "PASS" | "UNVERIFIED";
  evidenceState: "VERIFIED" | "UNVERIFIED";
  source: string;
  checkedAt: string;
  detail: string;
  hash: string;
}

function unverified(reason: string, sourceCommitSha: string | null = null): TestCiEvidenceSummary {
  return {
    status: "UNVERIFIED",
    reason,
    sourceCommitSha,
    runId: null,
    runUrl: null,
    runtime: { checkpointSelfTest: null, bootstrapReady: null, chainValid: null },
    requiredStepsSatisfied: false,
  };
}

/**
 * Core exact-SHA TEST/CI evidence evaluation. Pure function of its inputs so
 * it is fully unit-testable without network access; `evaluateTestCiEvidence`
 * below wires it to the real fetchers.
 */
export async function computeTestCiEvidence(
  attestation: ProductionRuntimeAttestation,
  githubGet: Fetcher
): Promise<TestCiEvidenceSummary> {
  if (!attestation.reachable) {
    return unverified("production_attestation_unreachable");
  }
  const sha = attestation.sourceCommitSha;
  if (!sha) {
    return unverified("missing_or_malformed_source_commit_sha");
  }
  if (attestation.checkpointSelfTest !== true) {
    return unverified("checkpoint_self_test_not_true", sha);
  }
  if (attestation.bootstrapReady !== true) {
    return unverified("bootstrap_ready_not_true", sha);
  }
  if (attestation.chainValid !== true) {
    return unverified("chain_valid_not_true", sha);
  }

  const runsPath =
    `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/` +
    `${encodeURIComponent(CANONICAL_WORKFLOW_PATH)}/runs` +
    `?head_sha=${encodeURIComponent(sha)}&status=success&per_page=20`;
  const runsResult = await githubGet(runsPath);
  if (!runsResult.ok || runsResult.json === undefined) {
    return unverified(`github_runs_fetch_failed:${runsResult.error ?? "unknown"}`, sha);
  }
  const runsJson = runsResult.json as Record<string, unknown>;
  const rawRuns = runsJson["workflow_runs"];
  if (!Array.isArray(rawRuns)) {
    return unverified("github_runs_malformed_payload", sha);
  }

  const canonicalRuns = rawRuns.filter((r): r is WorkflowRun => {
    if (r === null || typeof r !== "object") return false;
    const run = r as WorkflowRun;
    if (typeof run.head_sha !== "string" || run.head_sha.toLowerCase() !== sha) return false;
    if (run.status !== "completed" || run.conclusion !== "success") return false;
    if (run.name !== CANONICAL_WORKFLOW_NAME) return false;
    if (typeof run.path === "string" && !run.path.endsWith(CANONICAL_WORKFLOW_PATH)) return false;
    return true;
  });

  if (canonicalRuns.length === 0) {
    return unverified("no_matching_successful_canonical_run", sha);
  }
  if (canonicalRuns.length > 1) {
    return unverified("ambiguous_multiple_valid_canonical_runs", sha);
  }

  const run = canonicalRuns[0];
  const runId = typeof run.id === "number" ? run.id : null;
  if (runId === null) {
    return unverified("canonical_run_missing_id", sha);
  }

  const jobsPath = `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runs/${runId}/jobs`;
  const jobsResult = await githubGet(jobsPath);
  if (!jobsResult.ok || jobsResult.json === undefined) {
    return unverified(`github_jobs_fetch_failed:${jobsResult.error ?? "unknown"}`, sha);
  }
  const jobsJson = jobsResult.json as Record<string, unknown>;
  const rawJobs = jobsJson["jobs"];
  if (!Array.isArray(rawJobs)) {
    return unverified("github_jobs_malformed_payload", sha);
  }

  const validateJob = rawJobs.find((j): j is WorkflowJob => {
    if (j === null || typeof j !== "object") return false;
    return (j as WorkflowJob).name === CANONICAL_JOB_NAME;
  });
  if (!validateJob) {
    return unverified("validate_job_missing", sha);
  }
  if (validateJob.status !== "completed" || validateJob.conclusion !== "success") {
    return unverified("validate_job_not_successful", sha);
  }

  const rawSteps = validateJob.steps;
  if (!Array.isArray(rawSteps)) {
    return unverified("validate_job_steps_malformed", sha);
  }
  const steps = rawSteps.filter((s): s is JobStep => s !== null && typeof s === "object");
  const stepByName = new Map<string, JobStep>();
  for (const step of steps) {
    if (typeof step.name === "string") stepByName.set(step.name, step);
  }
  for (const requiredName of REQUIRED_STEP_NAMES) {
    const step = stepByName.get(requiredName);
    if (!step) {
      return unverified(`required_step_missing:${requiredName}`, sha);
    }
    if (step.status !== "completed" || step.conclusion !== "success") {
      return unverified(`required_step_not_successful:${requiredName}`, sha);
    }
  }

  const runUrl = typeof run.html_url === "string" ? sanitizeUrl(run.html_url) : sanitizeUrl(runsResult.url);

  return {
    status: "PASS",
    reason: "exact_sha_ci_and_runtime_predicates_satisfied",
    sourceCommitSha: sha,
    runId,
    runUrl,
    runtime: {
      checkpointSelfTest: attestation.checkpointSelfTest,
      bootstrapReady: attestation.bootstrapReady,
      chainValid: attestation.chainValid,
    },
    requiredStepsSatisfied: true,
  };
}

/** Deterministic SHA-256 hash over the bounded, non-secret evidence summary. */
export async function hashEvidenceSummary(summary: TestCiEvidenceSummary): Promise<string> {
  const canonical = JSON.stringify({
    status: summary.status,
    reason: summary.reason,
    sourceCommitSha: summary.sourceCommitSha,
    runId: summary.runId,
    runUrl: summary.runUrl,
    runtime: summary.runtime,
    requiredStepsSatisfied: summary.requiredStepsSatisfied,
  });
  const { createHash } = await import("node:crypto");
  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

export function detailForSummary(summary: TestCiEvidenceSummary): string {
  if (summary.status === "PASS") {
    return (
      `Exact deployed source commit ${summary.sourceCommitSha} has a completed successful ` +
      `"${CANONICAL_WORKFLOW_NAME}" run with a successful "${CANONICAL_JOB_NAME}" job and all ` +
      `required steps successful, and live production runtime self-test predicates are true.`
    );
  }
  return `TEST evidence UNVERIFIED: ${summary.reason}.`;
}

/**
 * Builds the full `test-ci-validation` evidence record given a runtime
 * attestation fetch function and a bounded GitHub fetch function. Kept
 * separate from `computeTestCiEvidence` so both can be unit tested with
 * fully synthetic fetchers (no network) in RED/GREEN tests.
 */
export async function buildTestCiValidationEvidence(
  fetchAttestation: () => Promise<ProductionRuntimeAttestation>,
  githubGet: Fetcher,
  now: () => Date = () => new Date()
): Promise<TestCiEvidenceRecord> {
  const attestation = await fetchAttestation();
  const summary = await computeTestCiEvidence(attestation, githubGet);
  const hash = await hashEvidenceSummary(summary);
  const source =
    summary.status === "PASS" && summary.runUrl
      ? summary.runUrl
      : `https://${GITHUB_API_HOST}/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${CANONICAL_WORKFLOW_PATH}`;
  return {
    id: TEST_CI_EVIDENCE_ID,
    subject: "Exact-source SARA-OMEGA TEST/CI validation",
    status: summary.status,
    evidenceState: summary.status === "PASS" ? "VERIFIED" : "UNVERIFIED",
    source,
    checkedAt: now().toISOString(),
    detail: detailForSummary(summary),
    hash,
  };
}
