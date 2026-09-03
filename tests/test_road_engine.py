from pathlib import Path

from road_engine import CERTIFICATION_ORDER, ROAD_TOOLS, RoadEngine


def engine(production=None, contextdev=None):
    return RoadEngine(
        release_version="3.2.1",
        hardening_profile="SIOS-V3.2-FAILSAFE-1",
        roadmap_path=Path(__file__).parents[1] / "data" / "roadmap.md",
        production_acceptance_supplier=lambda: production or {"production_accepted": False},
        contextdev_supplier=lambda: contextdev or {},
    )


def test_exposes_exact_road_tool_set():
    discovered = engine().tool_discovery()["tools"]
    assert [tool["name"] for tool in discovered] == list(ROAD_TOOLS)


def test_production_acceptance_only_passes_on_live_true():
    blocked = engine(production={"production_accepted": False}).get_production_acceptance()
    passing = engine(production={"production_accepted": True}).get_production_acceptance()
    assert blocked["status"] == "UNVERIFIED"
    assert passing["status"] == "PASS"


def test_contextdev_fails_closed_without_all_required_states():
    result = engine(
        contextdev={
            "commercial_authorization": "VERIFIED",
            "monetized_runtime": "ALLOWED",
            "production_authorization": "BLOCKED",
        }
    ).get_contextdev_authorization()
    assert result["status"] == "BLOCKED"


def test_release_cannot_skip_acceptance_or_signing():
    result = engine(production={"production_accepted": True}).verify_release_candidate(
        claimedPassedGates=["BUILD", "TEST", "SECURITY", "RELEASE"]
    )
    assert result["status"] == "BLOCKED"
    assert result["gate_status"]["RELEASE"] == "BLOCKED"


def test_openapi_request_schemas_include_properties():
    schema = engine().openapi_schema("https://sara-omega-production.up.railway.app")
    for path, methods in schema["paths"].items():
        if not path.startswith("/road/actions/"):
            continue
        request_schema = methods["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert request_schema["type"] == "object"
        assert "properties" in request_schema


def test_certification_order_is_authoritative():
    assert CERTIFICATION_ORDER[-3:] == ("ACCEPTANCE", "SIGN", "RELEASE")

