import importlib


def test_quantum_defense_road_status_blocks_release_until_live_gates_pass():
    road_gate = importlib.import_module(
        "quantum_defense_siso_road_singular_build.road_fusion.road_gate"
    )

    status = road_gate.road_status()

    assert status["local"] == "PASS"
    assert status["release"] == "BLOCKED"
    assert status["evidence_state"] == "CURRENTLY_INACCESSIBLE"
    assert status["missing"] == [
        "ACCEPTANCE",
        "SIGN",
        "PROMOTION_AUTHORITY",
    ]


def test_quantum_defense_claim_policy_blocks_overclaims():
    claim_policy = importlib.import_module(
        "quantum_defense_siso_road_singular_build.road_fusion.claim_policy"
    )

    results = claim_policy.evaluate_claims(
        [
            "SARA can defeat all rogue AI.",
            "SARA disables outside AI systems.",
            "SARA has FIPS validation.",
            claim_policy.SUPPORTED_SCOPE_LIMITED_CLAIM,
        ],
        evidence={},
    )

    statuses = {item["canonical_control"]: item["status"] for item in results}
    assert statuses["defeat all rogue AI"] == "BLOCKED_OVERSTATED"
    assert statuses["disables outside AI systems"] == "BLOCKED_UNSUPPORTED"
    assert (
        statuses["FIPS validation unless the actual crypto module and deployment are validated"]
        == "BLOCKED_UNLESS_FIPS_MODULE_AND_DEPLOYMENT_VALIDATED"
    )
    assert statuses["enterprise_rogue_ai_execution_containment"] == "SUPPORTED_SCOPE_LIMITED"


def test_quantum_defense_health_surface_is_fail_closed():
    app = importlib.import_module(
        "quantum_defense_siso_road_singular_build.road_fusion.aws_health_app"
    )

    health_status, _, health_body = app.route_request("/health")
    road_status, _, road_body = app.route_request("/road/status")
    claims_status, _, claims_body = app.route_request("/road/claims")
    missing_status, _, missing_body = app.route_request("/missing")

    assert health_status == 200
    assert '"release": "BLOCKED"' in health_body
    assert road_status == 200
    assert '"classification": "AWS_DEPLOYMENT_READY_RELEASE_BLOCKED_UNTIL_LIVE_ROAD_SIGN_ACCEPT_PROMOTION"' in road_body
    assert claims_status == 200
    assert "BLOCKED_OVERSTATED" in claims_body
    assert missing_status == 404
    assert '"status": "not_found"' in missing_body
