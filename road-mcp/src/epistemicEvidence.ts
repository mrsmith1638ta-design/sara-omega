import { createHash } from "node:crypto";

import { normalizeSourceCommitSha, sanitizeUrl, type ProductionRuntimeAttestation } from "./testEvidence.js";

export const EPISTEMIC_EVIDENCE_ID = "epistemic-claim-audit";
export const EPISTEMIC_REVIEW_URL =
  process.env.ROAD_EPISTEMIC_REVIEW_URL ?? "https://sara-omega-production.up.railway.app/epistemic/review";

const REQUEST_TIMEOUT_MS = 4500;
const MAX_PAYLOAD_BYTES = 128 * 1024;

export interface BoundedEpistemicResult {
  ok: boolean;
  status?: number;
  json?: unknown;
  error?: string;
  url: string;
}

export type EpistemicFetcher = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string }
) => Promise<BoundedEpistemicResult>;

export interface EpistemicEvidenceRecord {
  id: typeof EPISTEMIC_EVIDENCE_ID;
  subject: string;
  status: "PASS" | "BLOCKED" | "UNVERIFIED";
  evidenceState: "VERIFIED" | "UNVERIFIED";
  source: string;
  checkedAt: string;
  detail: string;
  hash: string;
}

async function boundedEpistemicJson(
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string }
): Promise<BoundedEpistemicResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      method: init?.method ?? "GET",
      redirect: "error",
      signal: controller.signal,
      headers: { Accept: "application/json", "User-Agent": "sara-omega-road-mcp", ...(init?.headers ?? {}) },
      body: init?.body,
    });
    const text = await response.text();
    if (Buffer.byteLength(text, "utf8") > MAX_PAYLOAD_BYTES) return { ok: false, error: "payload_too_large", url: sanitizeUrl(url) };
    if (!response.ok) return { ok: false, status: response.status, error: `http_${response.status}`, url: sanitizeUrl(url) };
    try {
      return { ok: true, status: response.status, json: JSON.parse(text), url: sanitizeUrl(url) };
    } catch {
      return { ok: false, error: "malformed_json", url: sanitizeUrl(url) };
    }
  } catch (error) {
    return { ok: false, error: `fetch_failed:${error instanceof Error ? error.message : "unknown_error"}`, url: sanitizeUrl(url) };
  } finally {
    clearTimeout(timer);
  }
}

function objectOrNull(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function unverified(reason: string): { status: "UNVERIFIED"; reason: string; sourceCommitSha: string | null } {
  return { status: "UNVERIFIED", reason, sourceCommitSha: null };
}

function probePayload(attestation: ProductionRuntimeAttestation, testDetail: string): string {
  return JSON.stringify({
    candidate_id: attestation.sourceCommitSha,
    claims: [
      {
        claim_id: "test-ci-validation-scope",
        text: "293 repository tests passed in the referenced validation run.",
        evidence_ids: ["test-ci-validation"],
      },
    ],
    evidence: [{ id: "test-ci-validation", status: "PASS", evidenceState: "VERIFIED", detail: testDetail }],
  });
}

export async function computeEpistemicEvidence(
  attestation: ProductionRuntimeAttestation,
  testDetail: string,
  fetcher: EpistemicFetcher
): Promise<{ status: "PASS" | "BLOCKED" | "UNVERIFIED"; reason: string; sourceCommitSha: string | null; raw?: Record<string, unknown> }> {
  if (!attestation.reachable || !attestation.sourceCommitSha) return unverified("production_attestation_unreachable_or_missing_sha");
  if (attestation.productionAccepted !== true) return { ...unverified("production_attestation_not_accepted"), sourceCommitSha: attestation.sourceCommitSha };
  const result = await fetcher(EPISTEMIC_REVIEW_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: probePayload(attestation, testDetail),
  });
  if (!result.ok || result.json === undefined) return { ...unverified(`epistemic_review_fetch_failed:${result.error ?? "unknown"}`), sourceCommitSha: attestation.sourceCommitSha };
  const raw = objectOrNull(result.json);
  if (!raw) return { ...unverified("epistemic_review_malformed_payload"), sourceCommitSha: attestation.sourceCommitSha };
  if (normalizeSourceCommitSha(raw["candidate_id"]) !== attestation.sourceCommitSha) return { ...unverified("epistemic_review_sha_mismatch"), sourceCommitSha: attestation.sourceCommitSha, raw };
  if (raw["can_pass"] !== false || raw["promotion_authority"] !== "NONE" || raw["execution_authority"] !== "NONE") {
    return { ...unverified("epistemic_review_authority_boundary_failed"), sourceCommitSha: attestation.sourceCommitSha, raw };
  }
  if (raw["decision"] === "BLOCKED") return { status: "BLOCKED", reason: "epistemic_claim_audit_blocked", sourceCommitSha: attestation.sourceCommitSha, raw };
  if (raw["decision"] !== "READY_FOR_VERIFICATION") return { ...unverified("epistemic_review_decision_unrecognized"), sourceCommitSha: attestation.sourceCommitSha, raw };
  if (!Array.isArray(raw["claims"]) || raw["claims"].some((claim) => objectOrNull(claim)?.["state"] !== "SUPPORTED")) {
    return { ...unverified("epistemic_review_contains_unsupported_claim"), sourceCommitSha: attestation.sourceCommitSha, raw };
  }
  return { status: "PASS", reason: "epistemic_claims_are_scope_consistent_and_exact_sha_bound", sourceCommitSha: attestation.sourceCommitSha, raw };
}

export async function buildEpistemicEvidence(
  fetchAttestation: () => Promise<ProductionRuntimeAttestation>,
  testDetail: string,
  fetcher: EpistemicFetcher = boundedEpistemicJson,
  now: () => Date = () => new Date()
): Promise<EpistemicEvidenceRecord> {
  const result = await computeEpistemicEvidence(await fetchAttestation(), testDetail, fetcher);
  const hash = createHash("sha256").update(JSON.stringify(result), "utf8").digest("hex");
  return {
    id: EPISTEMIC_EVIDENCE_ID,
    subject: "SARA-OMEGA Epistemic claim audit",
    status: result.status,
    evidenceState: result.status === "UNVERIFIED" ? "UNVERIFIED" : "VERIFIED",
    source: sanitizeUrl(EPISTEMIC_REVIEW_URL),
    checkedAt: now().toISOString(),
    detail:
      result.status === "PASS"
        ? `Epistemic claim audit for exact deployed source commit ${result.sourceCommitSha} found all submitted claims scope-consistent and preserved no promotion or execution authority.`
        : `Epistemic claim audit is ${result.status}: ${result.reason}.`,
    hash,
  };
}
