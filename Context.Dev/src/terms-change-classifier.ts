import type { AuthorizationState } from "./vendor-license-state";

const MATERIAL_TOPICS = new Set([
  "commercial rights", "automation", "ai agents", "retention",
  "intellectual property", "downstream distribution", "privacy",
  "termination", "indemnification", "authorization",
]);

export function classifyTermsChange(
  changed: boolean,
  stream: "LEGAL_LICENSE" | "TECHNICAL_API",
  topics: readonly string[],
): AuthorizationState | null {
  const material = changed && stream === "LEGAL_LICENSE" && topics.some((topic) => MATERIAL_TOPICS.has(topic.toLowerCase()));
  return material ? "REVALIDATION_REQUIRED" : null;
}
