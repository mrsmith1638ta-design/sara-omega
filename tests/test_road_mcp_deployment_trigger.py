from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_railway_deploys_when_road_mcp_changes() -> None:
    workflow = ROOT / ".github" / "workflows" / "railway-production-activate.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "- 'road-mcp/**'" in text
