import { createHash } from "node:crypto";

import { normalizeSourceCommitSha, sanitizeUrl, type ProductionRuntimeAttestation } from "./testEvidence.js";
import type { EvidenceRecord } from "./server.js";

export const ROAD_GATE_EVIDENCE_URL =
  process.env.ROAD_GATE_EVIDENCE_URL ?? "https://sara-omega-production.up.railway.app/road/gates/review";

export const ROAD_GATE_EVIDENCE_IDS = {
  GOVERNANCE: "governance-evidence",
  PRIVACY: "privacy-evidence",
  PERFORMANCE: "performance-evidence",
  RECOVERY: "recovery-evidence",
  "MULTI-CLOUD": "multi-cloud-evidence",
} as const;

type GateName = keyof typeof ROAD_GATE_EVIDENCE_IDS;
type FetchResult = { ok: boolean; status?: number; json?: unknown; error?: string; url: string };
type Fetcher = (url: string, init: { method: string; headers: Record<string, string>; body: string }) => Promise<FetchResult>;

interface GateResult { gate: GateName; status: "PASS" | "UNVERIFIED"; detail: string; evidence_state?: string }

function objectOrNull(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

async function boundedPost(url: string, init: { method: string; headers: Record<string, string>; body: string }): Promise<FetchResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 4500);
  try {
    const response = await fetch(url, { ...init, redirect: "error", signal: controller.signal });
    const text = await response.text();
    if (Buffer.byteLength(text, "utf8") > 128 * 1024) return { ok: false, error: "payload_too_large", url: sanitizeUrl(url) };
    if (!response.ok) return { ok: false, status: response.status, error: `http_${response.status}`, url: sanitizeUrl(url) };
    try { return { ok: true, status: response.status, json: JSON.parse(text), url: sanitizeUrl(url) }; }
    catch { return { ok: false, error: "malformed_json", url: sanitizeUrl(url) }; }
  } catch (error) {
    return { ok: false, error: `fetch_failed:${error instanceof Error ? error.message : "unknown_error"}`, url: sanitizeUrl(url) };
  } finally { clearTimeout(timer); }
}

function unverifiedRecords(reason: string, checkedAt: string): EvidenceRecord[] {
  return (Object.entries(ROAD_GATE_EVIDENCE_IDS) as [GateName, string][]).map(([gate, id]) => ({
    id,
    subject: `ROAD ${gate} gate evidence`,
    status: "UNVERIFIED",
    evidenceState: "UNVERIFIED",
    source: sanitizeUrl(ROAD_GATE_EVIDENCE_URL),
    checkedAt,
    detail: `ROAD gate evidence is UNVERIFIED: ${reason}.`,
    hash: createHash("sha256").update(`${id}:${reason}`, "utf8").digest("hex"),
  }));
}

export async function buildRoadGateEvidence(
  attestation: ProductionRuntimeAttestation,
  observations: EvidenceRecord[],
  fetcher: Fetcher = boundedPost,
  now: () => Date = () => new Date()
): Promise<EvidenceRecord[]> {
  const checkedAt = now().toISOString();
  if (!attestation.reachable || !attestation.sourceCommitSha || attestation.productionAccepted !== true) {
    return unverifiedRecords("production attestation is not reachable, exact-SHA bound, and accepted", checkedAt);
  }
  const started = Date.now();
  const providers = ["railway", "github-actions"];
  const result = await fetcher(ROAD_GATE_EVIDENCE_URL, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json", "User-Agent": "sara-omega-road-mcp" },
    body: JSON.stringify({
      candidate_id: attestation.sourceCommitSha,
      observations: observations.map(({ id, status, source, detail }) => ({ id, status, source, detail })),
      providers,
      probe_ms: Date.now() - started,
    }),
  });
  const raw = objectOrNull(result.json);
  const gates = raw && Array.isArray(raw["gates"]) ? raw["gates"] : [];
  if (!result.ok || !raw || normalizeSourceCommitSha(raw["candidate_id"]) !== attestation.sourceCommitSha || raw["decision"] !== "READY_FOR_VERIFICATION" || raw["can_pass"] !== false || raw["promotion_authority"] !== "NONE" || raw["execution_authority"] !== "NONE") {
    return unverifiedRecords(!result.ok ? result.error ?? "evidence endpoint unavailable" : "gate artifact failed exact-SHA or authority validation", checkedAt);
  }
  return (Object.entries(ROAD_GATE_EVIDENCE_IDS) as [GateName, string][]).map(([gate, id]) => {
    const found = gates.map(objectOrNull).find((item) => item?.["gate"] === gate) as GateResult | undefined;
    const status = found?.status === "PASS" ? "PASS" : "UNVERIFIED";
    const detail = found?.detail ?? `No ${gate} gate result was returned.`;
    return {
      id,
      subject: `ROAD ${gate} gate evidence`,
      status,
      evidenceState: status === "PASS" ? "VERIFIED" : "UNVERIFIED",
      source: sanitizeUrl(ROAD_GATE_EVIDENCE_URL),
      checkedAt,
      detail: `${detail} Exact deployed source commit: ${attestation.sourceCommitSha}.`,
      hash: createHash("sha256").update(JSON.stringify({ gate, status, detail, sha: attestation.sourceCommitSha }), "utf8").digest("hex"),
    };
  });
}
