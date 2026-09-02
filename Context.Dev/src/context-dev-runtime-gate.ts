import type { VendorLicenseState } from "./vendor-license-state";

export interface RuntimeRequest {
  monetized: boolean;
  automated: boolean;
  targetSiteRightsValid: boolean;
  sensitive: boolean;
  requiresZdr: boolean;
  zdrVerified: boolean;
}

export interface GateDecision {
  allowed: boolean;
  denials: readonly string[];
}

export function evaluateContextDevRequest(request: RuntimeRequest, state: VendorLicenseState): GateDecision {
  const denials: string[] = [];
  if (request.monetized && state.authorizationState !== "VERIFIED") denials.push("COMMERCIAL_AUTHORIZATION_NOT_VERIFIED");
  if (!state.storedTermsHash || state.storedTermsHash !== state.currentVerifiedTermsHash) denials.push("TERMS_HASH_MISMATCH");
  if (request.automated && !state.automatedUseAuthorized) denials.push("AUTOMATED_USE_NOT_AUTHORIZED");
  if (!request.targetSiteRightsValid) denials.push("TARGET_SITE_RIGHTS_FAILED");
  if (request.sensitive && request.requiresZdr && !request.zdrVerified) denials.push("ZDR_NOT_VERIFIED");
  return { allowed: denials.length === 0, denials };
}
