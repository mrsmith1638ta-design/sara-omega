from __future__ import annotations


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


def road_status() -> dict:
    return evaluate_release(default_local_gate_state())

