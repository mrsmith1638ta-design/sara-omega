export type AuthorizationState =
  | "UNVERIFIED"
  | "PENDING_WRITTEN_AUTHORIZATION"
  | "VERIFIED"
  | "REVALIDATION_REQUIRED"
  | "SUSPENDED";

export interface EvidenceLedgerEntry {
  vendor: string;
  sourceUrl: string;
  documentTitle: string;
  retrievedAt: string;
  effectiveDate: string | null;
  termsVersion: string;
  sha256ContentHash: string;
  claim: string;
  evidenceExcerptReference: string;
  epistemicClassification: string;
  authorizationScope: readonly string[];
  supersededBy: string | null;
  reviewer: string;
  approvalState: "PENDING" | "APPROVED" | "REJECTED" | "SUPERSEDED";
}

export interface VendorLicenseState {
  authorizationState: AuthorizationState;
  authorizedScopes: ReadonlySet<string>;
  storedTermsHash: string | null;
  currentVerifiedTermsHash: string | null;
  automatedUseAuthorized: boolean;
  evidence: readonly EvidenceLedgerEntry[];
}
