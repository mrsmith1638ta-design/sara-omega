import json

from .models import Problem, ProblemMap


class ProblemEngine:
    def map(self, p: Problem) -> ProblemMap:
        objective = p.objective or p.query
        unknowns = []
        if not p.context:
            unknowns.append("No structured external context was supplied.")

        facts = [f"User query: {p.query}"]
        constraints = [f"Authority level: {p.authority_level}"]
        risks = []

        try:
            from .iot.service import IoTService

            iot_context = IoTService().context_for_problem(p.query, p.context)
        except Exception:
            iot_context = None
        if iot_context:
            facts.append(
                "Validated IoT evidence: "
                + json.dumps(iot_context, sort_keys=True, separators=(",", ":"), default=str)[:12000]
            )
            constraints.append(
                "IoT observations are evidence, not automatic execution authority; sensor repetition cannot independently verify a physical root cause."
            )
            risks.append("Do not promote IoT anomaly evidence into verified hardware failure without stronger independent evidence.")

        return ProblemMap(
            objective=objective,
            facts=facts,
            constraints=constraints,
            assumptions=["Provider outputs require verification before being treated as established facts."],
            unknowns=unknowns,
            risks=risks,
            subtasks=[]
        )
