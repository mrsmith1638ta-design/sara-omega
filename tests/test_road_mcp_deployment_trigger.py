import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_railway_deploys_when_road_mcp_changes() -> None:
    workflow = ROOT / ".github" / "workflows" / "railway-production-activate.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "- 'road-mcp/**'" in text


def test_road_mcp_has_dedicated_railway_deploy_workflow() -> None:
    workflow = ROOT / ".github" / "workflows" / "road-mcp-railway-deploy.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "working-directory: road-mcp" in text
    assert "railway up --service sara-omega-road-mcp --ci" in text
    assert "495f4e9d-1f63-4511-8a02-a971452e9170" in text
    assert "- 'road-mcp/**'" in text


def test_road_mcp_railway_healthcheck_uses_http_health_route() -> None:
    config = json.loads((ROOT / "road-mcp" / "railway.json").read_text(encoding="utf-8"))

    assert config["deploy"]["healthcheckPath"] == "/health"
