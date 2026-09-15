from __future__ import annotations

import os
from collections.abc import Mapping


LOCAL_REQUIRED_GATES = ("BUILD", "TEST", "SECURITY", "ADVERSARIAL")
RELEASE_REQUIRED_GATES = ("ACCEPTANCE", "SIGN", "PROMOTION_AUTHORITY")


def evaluate_release(gates: dict[str, str]) -> dict:
    missing = [
        gate
        for gate in (*LOCAL_REQUIRED_GATES, *RELEASE_REQUIRED_GATES)
        if gates.get(gate) != "PASS"
    ]
    local_pass = all(gates.get(gate) == "PASS" for gate in LOCAL_REQUIRED_GATES)
    release_pass = not missing
    return {
        "service": "sara-quantum-defense-road-fusion",
        "local": "PASS" if local_pass else "BLOCKED",
        "release": "PASS" if release_pass else "BLOCKED",
        "evidence_state": "VERIFIED" if release_pass else "CURRENTLY_INACCESSIBLE",
        "missing": missing,
        "required_for_release": list(RELEASE_REQUIRED_GATES),
        "classification": "AWS_DEPLOYMENT_READY_RELEASE_BLOCKED_UNTIL_LIVE_ROAD_SIGN_ACCEPT_PROMOTION"
        if local_pass and not release_pass
        else "ROAD_RELEASE_PASS",
    }


def default_local_gate_state() -> dict[str, str]:
    return {
        "BUILD": "PASS",
        "TEST": "PASS",
        "SECURITY": "PASS",
        "ADVERSARIAL": "PASS",
        "ACCEPTANCE": "CURRENTLY_INACCESSIBLE",
        "SIGN": "CURRENTLY_INACCESSIBLE",
        "PROMOTION_AUTHORITY": "CURRENTLY_INACCESSIBLE",
    }


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(char in "0123456789abcdefABCDEF" for char in value)


def _release_gate_state(evidence: Mapping[str, object] | None = None) -> dict[str, str]:
    gates = default_local_gate_state()
    evidence = evidence or {}

    acceptance = evidence.get("acceptance")
    if (
        isinstance(acceptance, Mapping)
        and acceptance.get("status") == "PASS"
        and acceptance.get("production_accepted") is True
        and bool(str(acceptance.get("source", "")).strip())
    ):
        gates["ACCEPTANCE"] = "PASS"

    sign = evidence.get("sign")
    if (
        isinstance(sign, Mapping)
        and sign.get("status") == "PASS"
        and _valid_sha256(sign.get("artifact_sha256"))
        and bool(str(sign.get("signature_ref", "")).strip())
    ):
        gates["SIGN"] = "PASS"

    promotion = evidence.get("promotion_authority")
    if (
        isinstance(promotion, Mapping)
        and promotion.get("status") == "APPROVED"
        and bool(str(promotion.get("approver", "")).strip())
        and bool(str(promotion.get("scope", "")).strip())
    ):
        gates["PROMOTION_AUTHORITY"] = "PASS"

    return gates


def road_status(evidence: Mapping[str, object] | None = None) -> dict:
    return evaluate_release(_release_gate_state(evidence))


def road_status_from_environment(environ: Mapping[str, str] | None = None) -> dict:
    environ = environ or os.environ
    evidence = {
        "acceptance": {
            "status": environ.get("SARA_AWS_ROAD_ACCEPTANCE", ""),
            "production_accepted": environ.get("SARA_AWS_PRODUCTION_ACCEPTED", "").lower() == "true",
            "source": environ.get("SARA_AWS_ACCEPTANCE_SOURCE", ""),
        },
        "sign": {
            "status": environ.get("SARA_AWS_ARTIFACT_SIGNING", ""),
            "artifact_sha256": environ.get("SARA_AWS_ARTIFACT_SHA256", ""),
            "signature_ref": environ.get("SARA_AWS_SIGNATURE_REF", ""),
        },
        "promotion_authority": {
            "status": environ.get("SARA_AWS_PROMOTION_AUTHORITY", ""),
            "approver": environ.get("SARA_AWS_PROMOTION_APPROVER", ""),
            "scope": environ.get("SARA_AWS_PROMOTION_SCOPE", ""),
        },
    }
    return road_status(evidence=evidence)
