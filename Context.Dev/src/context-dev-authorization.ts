import type { EvidenceLedgerEntry, VendorLicenseState } from "./vendor-license-state";

const SHA256 = /^[a-f0-9]{64}$/;

export function hasApprovedScope(state: VendorLicenseState, scope: string): boolean {
  return state.authorizedScopes.has(scope) && state.evidence.some((entry: EvidenceLedgerEntry) =>
    entry.approvalState === "APPROVED" &&
    entry.epistemicClassification === "VERIFIED" &&
    entry.supersededBy === null &&
    entry.authorizationScope.includes(scope) &&
    SHA256.test(entry.sha256ContentHash),
  );
}
