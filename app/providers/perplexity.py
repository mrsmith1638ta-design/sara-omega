import os, httpx
from .base import Specialist
from ..models import Assignment, SpecialistResult, Evidence, Claim

class PerplexitySpecialist(Specialist):
    name = "perplexity"
    def __init__(self):
        self.key = os.getenv("PERPLEXITY_API_KEY")
        self.model = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
        self.url = "https://api.perplexity.ai/v1/sonar"

    async def run(self, assignment: Assignment) -> SpecialistResult:
        if not self.key:
            return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task,
                                    success=False, error="PERPLEXITY_API_KEY is not configured.")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are SARA-OMEGA's research specialist. Separate evidence from inference and cite current sources."},
                {"role": "user", "content": assignment.task}
            ],
            "web_search_options": {"search_mode": "web"}
        }
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(self.url, headers={"Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json"}, json=payload)
                r.raise_for_status()
                data = r.json()
            answer = data["choices"][0]["message"]["content"]
            ev = [Evidence(source=x.get("url",""), title=x.get("title"), date=x.get("date"),
                           snippet=x.get("snippet"), provider=self.name)
                  for x in data.get("search_results", []) if x.get("url")]
            claim = Claim(provider=self.name, statement=answer, evidence=ev,
                          confidence=0.65 if ev else 0.45)
            return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task,
                                    answer=answer, claims=[claim], evidence=ev, raw={"model": data.get("model")})
        except Exception as e:
            return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task,
                                    success=False, error=str(e))
