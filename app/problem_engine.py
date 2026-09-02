from .models import Problem, ProblemMap

class ProblemEngine:
    def map(self, p: Problem) -> ProblemMap:
        objective = p.objective or p.query
        unknowns = []
        if not p.context:
            unknowns.append("No structured external context was supplied.")
        return ProblemMap(
            objective=objective,
            facts=[f"User query: {p.query}"],
            constraints=[f"Authority level: {p.authority_level}"],
            assumptions=["Provider outputs require verification before being treated as established facts."],
            unknowns=unknowns,
            risks=[],
            subtasks=[]
        )
