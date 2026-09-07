from .models import Assignment, Problem, ProblemMap

RESEARCH = ("current", "latest", "market", "competitor", "regulation", "research", "source", "evidence", "price", "news")
CODE = ("code", "implement", "build", "bug", "test", "deploy", "architecture", "software", "api")
REPO = ("repository", "repo", "codebase", "refactor", "existing code", "files")
DATA_ANALYTICS = (
    "analytics", "analyze data", "business intelligence", "cohort", "conversion",
    "dashboard", "dataset", "forecast", "kpi", "metric", "metrics", "reporting",
    "statistics", "telemetry", "trend"
)

class OmegaRouter:
    def route(self, p: Problem, m: ProblemMap) -> list[Assignment]:
        text = f"{p.query} {p.objective or ''}".lower()
        out: list[Assignment] = []
        if any(k in text for k in RESEARCH):
            out.append(Assignment(provider="perplexity", role="research/evidence", task=p.query))
        if any(k in text for k in CODE):
            out.append(Assignment(provider="codex", role="engineering", task=p.query))
        if any(k in text for k in REPO):
            out.append(Assignment(provider="cursor", role="repository analysis", task=p.query))
        if any(k in text for k in DATA_ANALYTICS):
            out.append(Assignment(provider="data_analytics", role="data analytics", task=p.query))
        return out
