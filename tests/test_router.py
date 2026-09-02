from app.router import OmegaRouter
from app.models import Problem
from app.problem_engine import ProblemEngine

def route(q, council=None):
    p=Problem(query=q,council=council)
    return {a.provider for a in OmegaRouter().route(p,ProblemEngine().map(p))}

def test_research_routes_perplexity():
    assert "perplexity" in route("Research the latest market regulation")

def test_code_routes_codex():
    assert "codex" in route("Implement and test this API")

def test_repo_routes_cursor():
    assert "cursor" in route("Inspect this repository and existing codebase")

def test_data_analytics_routes_expansion_provider():
    assert "data_analytics" in route("Analyze dashboard metrics and telemetry trends")

def test_forced_council_routes_all():
    assert route("Evaluate this decision", True) == {"perplexity","codex","cursor","data_analytics"}
