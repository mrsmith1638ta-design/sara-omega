from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


EpistemicState = Literal["SUPPORTED", "OVERSTATED", "CONTRADICTED", "UNVERIFIED"]
EpistemicDecision = Literal["BLOCKED", "READY_FOR_VERIFICATION"]


class EpistemicClaim(BaseModel):
    claim_id: str = Field(default="claim", max_length=128)
    text: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)


class EpistemicReviewRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=128)
    claims: list[EpistemicClaim] = Field(default_factory=list, max_length=64)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=128)


class EpistemicAgent:
    """Audits whether release claims are no broader than their evidence.

    This is a claim-scope gate, not a source-code reviewer. It can block an
    overconfident claim, but it cannot certify, promote, or execute a release.
    """

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-epistemic-agent",
            "role": "claim_scope_and_evidence_justification_gate",
            "can_block": True,
            "can_pass": False,
            "promotion_authority": "NONE",
            "execution_authority": "NONE",
            "boundary": "audits claims about evidence; never certifies production PASS",
        }

    def review(self, request: EpistemicReviewRequest) -> dict[str, Any]:
        evidence_by_id = {str(item.get("id")): item for item in request.evidence if item.get("id")}
        audited = [self._audit_claim(claim, evidence_by_id) for claim in request.claims]
        blocking = [item for item in audited if item["state"] in {"OVERSTATED", "CONTRADICTED", "UNVERIFIED"}]
        decision: EpistemicDecision = "BLOCKED" if blocking else "READY_FOR_VERIFICATION"
        return {
            "service": "sara-epistemic-agent",
            "candidate_id": request.candidate_id,
            "decision": decision,
            "can_block": True,
            "can_pass": False,
            "promotion_authority": "NONE",
            "execution_authority": "NONE",
            "claims": audited,
            "summary": {
                "claim_count": len(audited),
                "supported": sum(item["state"] == "SUPPORTED" for item in audited),
                "overstated": sum(item["state"] == "OVERSTATED" for item in audited),
                "contradicted": sum(item["state"] == "CONTRADICTED" for item in audited),
                "unverified": sum(item["state"] == "UNVERIFIED" for item in audited),
            },
            "boundary": "Epistemic narrows or blocks claims; ROAD/Governance owns release authority.",
        }

    def _audit_claim(self, claim: EpistemicClaim, evidence_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
        linked = [evidence_by_id[evidence_id] for evidence_id in claim.evidence_ids if evidence_id in evidence_by_id]
        base = {"claim_id": claim.claim_id, "original_claim": claim.text, "evidence_ids": claim.evidence_ids}
        if not linked or len(linked) != len(claim.evidence_ids):
            return {**base, "state": "UNVERIFIED", "reason": "claim references missing evidence", "corrected_claim": None}
        if any(item.get("status") != "PASS" or item.get("evidenceState") != "VERIFIED" for item in linked):
            return {**base, "state": "CONTRADICTED", "reason": "linked evidence is not PASS/VERIFIED", "corrected_claim": None}

        text = claim.text.strip()
        lower = text.lower()
        detail = " ".join(str(item.get("detail", "")) for item in linked)
        if ("all production tests" in lower or "all tests passed" in lower) and "repository tests" in detail.lower():
            corrected = self._repository_test_correction(detail)
            return {
                **base,
                "state": "OVERSTATED",
                "reason": "claim scope includes production or all tests, while evidence only establishes repository tests",
                "corrected_claim": corrected,
            }
        if "production acceptance" in lower and not any("production" in str(item.get("subject", "")).lower() for item in linked):
            return {
                **base,
                "state": "OVERSTATED",
                "reason": "claim names production acceptance but linked evidence does not establish that subject",
                "corrected_claim": None,
            }
        return {**base, "state": "SUPPORTED", "reason": "claim scope is consistent with linked PASS/VERIFIED evidence", "corrected_claim": text}

    @staticmethod
    def _repository_test_correction(detail: str) -> str:
        match = re.search(r"(\d+\s+repository tests passed(?:\s+in validation run\s+[^.\s]+)?)", detail, re.IGNORECASE)
        if match:
            return f"{match.group(1).strip()}."
        return "The referenced validation evidence establishes repository test results only."
