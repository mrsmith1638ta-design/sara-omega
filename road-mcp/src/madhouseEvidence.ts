import { createHash } from "node:crypto";

import { normalizeSourceCommitSha, sanitizeUrl, type ProductionRuntimeAttestation } from "./testEvidence.js";

export const MADHOUSE_ADVERSARIAL_EVIDENCE_ID = "madhouse-adversarial-review";

export const MADHOUSE_HEALTH_URL =
  process.env.ROAD_MADHOUSE_HEALTH_URL ?? "https://sara-omega-production.up.railway.app/madhouse/health";
export const MADHOUSE_REVIEW_URL =
  process.env.ROAD_MADHOUSE_REVIEW_URL ?? "https://sara-omega-production.up.railway.app/madhouse/review";

const REQUEST_TIMEOUT_MS = 4500;
const MAX_PAYLOAD_BYTES = 128 * 1024;

export interface BoundedMadhouseResult {
  ok: boolean;
  status?: number;
  json?: unknown;
  error?: string;
  url: string;
}

export type MadhouseFetcher = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string }
) => Promise<BoundedMadhouseResult>;

export interface MadhouseEvidenceSummary {
  status: "PASS" | "BLOCKED" | "UNVERIFIED";
  reason: string;
  sourceCommitSha: string | null;
  health: {
    canBlock: boolean | null;
    canPass: boolean | null;
    promotionAuthority: string | null;
  };
  review: {
    candidateId: string | null;
    decision: string | null;
    canPass: boolean | null;
    promotionAuthority: string | null;
    executionAuthority: string | null;
    findingCount: number | null;
    evidenceLedgerCount: number | null;
    failureFingerprints: string[];
    requiredValidation: string[];
  };
}

export interface MadhouseEvidenceRecord {
  id: typeof MADHOUSE_ADVERSARIAL_EVIDENCE_ID;
  subject: string;
  status: "PASS" | "BLOCKED" | "UNVERIFIED";
  evidenceState: "VERIFIED" | "UNVERIFIED";
  source: string;
  checkedAt: string;
  detail: string;
  hash: string;
}

export async function boundedMadhouseJson(
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string }
): Promise<BoundedMadhouseResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: init?.method ?? "GET",
      redirect: "error",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "User-Agent": "sara-omega-road-mcp",
        ...(init?.headers ?? {}),
      },
      body: init?.body,
    });
    const text = await res.text();
    if (Buffer.byteLength(text, "utf8") > MAX_PAYLOAD_BYTES) {
      return { ok: false, error: "payload_too_large", url: sanitizeUrl(url) };
    }
    if (!res.ok) {
      return { ok: false, status: res.status, error: `http_${res.status}`, url: sanitizeUrl(url) };
    }
    try {
      return { ok: true, status: res.status, json: JSON.parse(text), url: sanitizeUrl(url) };
    } catch {
      return { ok: false, error: "malformed_json", url: sanitizeUrl(url) };
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "unknown_error";
    return { ok: false, error: `fetch_failed:${message}`, url: sanitizeUrl(url) };
  } finally {
    clearTimeout(timer);
  }
}

function unverified(reason: string, sourceCommitSha: string | null = null): MadhouseEvidenceSummary {
  return {
    status: "UNVERIFIED",
    reason,
    sourceCommitSha,
    health: { canBlock: null, canPass: null, promotionAuthority: null },
    review: {
      candidateId: null,
      decision: null,
      canPass: null,
      promotionAuthority: null,
      executionAuthority: null,
      findingCount: null,
      evidenceLedgerCount: null,
      failureFingerprints: [],
      requiredValidation: [],
    },
  };
}

function objectOrNull(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function healthSummary(raw: Record<string, unknown>): MadhouseEvidenceSummary["health"] {
  return {
    canBlock: typeof raw["can_block"] === "boolean" ? raw["can_block"] : null,
    canPass: typeof raw["can_pass"] === "boolean" ? raw["can_pass"] : null,
    promotionAuthority: typeof raw["promotion_authority"] === "string" ? raw["promotion_authority"] : null,
  };
}

function reviewSummary(raw: Record<string, unknown>): MadhouseEvidenceSummary["review"] {
  return {
    candidateId: normalizeSourceCommitSha(raw["candidate_id"]),
    decision: typeof raw["decision"] === "string" ? raw["decision"] : null,
    canPass: typeof raw["can_pass"] === "boolean" ? raw["can_pass"] : null,
    promotionAuthority: typeof raw["promotion_authority"] === "string" ? raw["promotion_authority"] : null,
    executionAuthority: typeof raw["execution_authority"] === "string" ? raw["execution_authority"] : null,
    findingCount: Array.isArray(raw["findings"]) ? raw["findings"].length : null,
    evidenceLedgerCount: Array.isArray(raw["evidence_ledger"]) ? raw["evidence_ledger"].length : null,
    failureFingerprints: stringArray(raw["failure_fingerprints"]),
    requiredValidation: stringArray(raw["required_validation"]),
  };
}

function madhouseProbePayload(sourceCommitSha: string): string {
  return JSON.stringify({
    candidate_id: sourceCommitSha,
    language: "python",
    generated_code:
      "def sara_omega_madhouse_candidate_probe():\n" +
      `    return {"source_commit_sha": "${sourceCommitSha}", "ready_for_verification": True}\n`,
    requirements: [
      "Bind Madhouse adversarial review evidence to the exact deployed source_commit_sha.",
      "Madhouse may block candidates but must never grant PASS or production promotion authority.",
    ],
    previous_failures: [],
    context: {
      source_commit_sha: sourceCommitSha,
      road_gate: "ADVERSARIAL",
      evidence_contract: MADHOUSE_ADVERSARIAL_EVIDENCE_ID,
    },
  });
}

export async function computeMadhouseAdversarialEvidence(
  attestation: ProductionRuntimeAttestation,
  fetcher: MadhouseFetcher
): Promise<MadhouseEvidenceSummary> {
  if (!attestation.reachable) return unverified("production_attestation_unreachable");
  const sha = attestation.sourceCommitSha;
  if (!sha) return unverified("missing_or_malformed_source_commit_sha");
  if (attestation.productionAccepted !== true) return unverified("production_attestation_not_accepted", sha);

  const healthResult = await fetcher(MADHOUSE_HEALTH_URL);
  if (!healthResult.ok || healthResult.json === undefined) {
    return unverified(`madhouse_health_fetch_failed:${healthResult.error ?? "unknown"}`, sha);
  }
  const healthRaw = objectOrNull(healthResult.json);
  if (!healthRaw) return unverified("madhouse_health_malformed_payload", sha);
  const health = healthSummary(healthRaw);
  if (
    healthRaw["service"] !== "sara-madhouse-agent" ||
    health.canBlock !== true ||
    health.canPass !== false ||
    health.promotionAuthority !== "NONE"
  ) {
    return { ...unverified("madhouse_health_authority_boundary_failed", sha), health };
  }

  const reviewResult = await fetcher(MADHOUSE_REVIEW_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: madhouseProbePayload(sha),
  });
  if (!reviewResult.ok || reviewResult.json === undefined) {
    return { ...unverified(`madhouse_review_fetch_failed:${reviewResult.error ?? "unknown"}`, sha), health };
  }
  const reviewRaw = objectOrNull(reviewResult.json);
  if (!reviewRaw) return { ...unverified("madhouse_review_malformed_payload", sha), health };
  const review = reviewSummary(reviewRaw);
  if (review.candidateId !== sha) {
    return { ...unverified("madhouse_review_sha_mismatch", sha), health, review };
  }
  if (review.canPass !== false || review.promotionAuthority !== "NONE" || review.executionAuthority !== "NONE") {
    return { ...unverified("madhouse_review_authority_boundary_failed", sha), health, review };
  }
  if (review.decision === "BLOCKED") {
    return {
      status: "BLOCKED",
      reason: "madhouse_review_blocked",
      sourceCommitSha: sha,
      health,
      review,
    };
  }
  if (review.decision !== "READY_FOR_VERIFICATION") {
    return { ...unverified("madhouse_review_decision_unrecognized", sha), health, review };
  }
  return {
    status: "PASS",
    reason: "madhouse_boundary_and_exact_sha_review_artifact_verified",
    sourceCommitSha: sha,
    health,
    review,
  };
}

export function detailForMadhouseSummary(summary: MadhouseEvidenceSummary): string {
  if (summary.status === "PASS") {
    return (
      `Madhouse adversarial review artifact for exact deployed source commit ${summary.sourceCommitSha} ` +
      "is READY_FOR_VERIFICATION, preserves can_pass=false, promotion_authority=NONE, " +
      "execution_authority=NONE, and exposes review ledger/fingerprint artifacts for ROAD."
    );
  }
  if (summary.status === "BLOCKED") {
    return (
      `ADVERSARIAL is BLOCKED because Madhouse blocked exact deployed source commit ${summary.sourceCommitSha} ` +
      `with ${summary.review.findingCount ?? 0} finding(s).`
    );
  }
  return `Madhouse adversarial evidence UNVERIFIED: ${summary.reason}.`;
}

export async function hashMadhouseEvidenceSummary(summary: MadhouseEvidenceSummary): Promise<string> {
  const canonical = JSON.stringify({
    status: summary.status,
    reason: summary.reason,
    sourceCommitSha: summary.sourceCommitSha,
    health: summary.health,
    review: summary.review,
  });
  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

export async function buildMadhouseAdversarialEvidence(
  fetchAttestation: () => Promise<ProductionRuntimeAttestation>,
  fetcher: MadhouseFetcher = boundedMadhouseJson,
  now: () => Date = () => new Date()
): Promise<MadhouseEvidenceRecord> {
  const attestation = await fetchAttestation();
  const summary = await computeMadhouseAdversarialEvidence(attestation, fetcher);
  const hash = await hashMadhouseEvidenceSummary(summary);
  return {
    id: MADHOUSE_ADVERSARIAL_EVIDENCE_ID,
    subject: "SARA-OMEGA Madhouse adversarial review",
    status: summary.status,
    evidenceState: summary.status === "UNVERIFIED" ? "UNVERIFIED" : "VERIFIED",
    source: sanitizeUrl(MADHOUSE_REVIEW_URL),
    checkedAt: now().toISOString(),
    detail: detailForMadhouseSummary(summary),
    hash,
  };
}
