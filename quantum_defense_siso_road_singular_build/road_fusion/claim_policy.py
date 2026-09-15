from __future__ import annotations

from typing import Iterable


CONTROLLED_CLAIMS = {
    "defeat all rogue AI": {
        "status": "BLOCKED_OVERSTATED",
        "reason": "Absolute all-systems rogue-AI defeat is not provable. Scope must be limited to protected enterprise SARA environments.",
    },
    "disables outside AI systems": {
        "status": "BLOCKED_UNSUPPORTED",
        "reason": "Outside AI systems are not under this build's legal or technical control unless explicitly owned and integrated.",
    },
    "FIPS validation unless the actual crypto module and deployment are validated": {
        "status": "BLOCKED_UNLESS_FIPS_MODULE_AND_DEPLOYMENT_VALIDATED",
        "reason": "FIPS validation requires validated cryptographic module and deployment evidence.",
    },
    "FIPS validated": {
        "status": "BLOCKED_UNLESS_FIPS_MODULE_AND_DEPLOYMENT_VALIDATED",
        "reason": "FIPS validation requires NIST CMVP/FIPS 140-3 module validation evidence for the exact module and deployment.",
    },
}

SUPPORTED_SCOPE_LIMITED_CLAIM = (
    "SARA prevents unauthorized rogue-AI execution attempts inside a protected enterprise SARA environment."
)


def evaluate_claims(claims: Iterable[str], evidence: dict | None = None) -> list[dict]:
    evidence = evidence or {}
    results: list[dict] = []
    fips_validated = bool(evidence.get("fips_module_validated") and evidence.get("deployment_validated"))
    outside_systems_integrated = bool(evidence.get("outside_ai_systems_owned_and_integrated"))

    for claim in claims:
        normalized = claim.lower()
        if "defeat all rogue ai" in normalized:
            status = "SUPPORTED_SCOPE_LIMITED" if evidence.get("scope_limited_enterprise_control") else "BLOCKED_OVERSTATED"
            results.append({"claim": claim, "status": status, "canonical_control": "defeat all rogue AI"})
        elif "disables outside ai systems" in normalized:
            status = "SUPPORTED_SCOPE_LIMITED" if outside_systems_integrated else "BLOCKED_UNSUPPORTED"
            results.append({"claim": claim, "status": status, "canonical_control": "disables outside AI systems"})
        elif "fips validation" in normalized or "fips validated" in normalized:
            status = "VERIFIED" if fips_validated else "BLOCKED_UNLESS_FIPS_MODULE_AND_DEPLOYMENT_VALIDATED"
            results.append({"claim": claim, "status": status, "canonical_control": "FIPS validation unless the actual crypto module and deployment are validated"})
        elif claim == SUPPORTED_SCOPE_LIMITED_CLAIM:
            results.append({"claim": claim, "status": "SUPPORTED_SCOPE_LIMITED", "canonical_control": "enterprise_rogue_ai_execution_containment"})
        else:
            results.append({"claim": claim, "status": "UNVERIFIED", "canonical_control": "none"})
    return results


def policy_manifest() -> dict:
    return {
        "claim_policy": "ROAD_TRUTH_GATED",
        "controlled_claims": CONTROLLED_CLAIMS,
        "supported_scope_limited_claim": SUPPORTED_SCOPE_LIMITED_CLAIM,
    }

