from .models import Assignment, Problem, ProblemMap
from .science.router import ScienceRouter

RESEARCH = ("current", "latest", "market", "competitor", "regulation", "research", "source", "evidence", "price", "news")
CODE = ("code", "implement", "build", "bug", "test", "deploy", "architecture", "software", "api")
REPO = ("repository", "repo", "codebase", "refactor", "existing code", "files")
DATA_ANALYTICS = (
    "analytics", "analyze data", "business intelligence", "cohort", "conversion",
    "dashboard", "dataset", "forecast", "kpi", "metric", "metrics", "reporting",
    "statistics", "telemetry", "trend"
)

SCIENCE_PROVIDER_MAP = {
    "ancient_egypt": ("science_ancient_egypt", "ancient Egyptian mathematics"),
    "classical_greek_roman": ("science_classical_greek_roman", "Greek/Roman construction mathematics"),
    "engineering": ("science_engineering", "modern engineering physics"),
    "maglev_ems": ("science_maglev_ems", "EMS maglev physics"),
    "maglev_eds": ("science_maglev_eds", "EDS maglev physics"),
    "maglev_hts": ("science_maglev_hts", "HTS levitation physics"),
}

class OmegaRouter:
    def __init__(self):
        self.science_router = ScienceRouter()

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
        for domain in self.science_router.route_text(text):
            provider, role = SCIENCE_PROVIDER_MAP[domain]
            out.append(Assignment(provider=provider, role=role, task=p.query))
        deduped: list[Assignment] = []
        seen: set[str] = set()
        for assignment in out:
            if assignment.provider not in seen:
                deduped.append(assignment)
                seen.add(assignment.provider)
        return deduped
