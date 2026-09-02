from __future__ import annotations
import asyncio, os
from .models import *
from .governance import GovernanceEngine
from .authority import AuthorityEngine
from .problem_engine import ProblemEngine
from .router import OmegaRouter
from .verification import EvidenceVerifier
from .memory import DecisionLedger
from .providers.perplexity import PerplexitySpecialist
from .providers.local_agents import CodexSpecialist, CursorSpecialist
from .providers.openai_judge import OpenAIJudge
from .providers.data_analytics import DataAnalyticsSpecialist

class SaraOmega:
    def __init__(self):
        self.governance = GovernanceEngine(os.getenv("SARA_POLICY_FILE", "./config/policies.json"))
        self.authority = AuthorityEngine()
        self.problem_engine = ProblemEngine()
        self.router = OmegaRouter()
        self.verifier = EvidenceVerifier()
        self.ledger = DecisionLedger()
        self.judge = OpenAIJudge()
        self.providers = {
            "perplexity": PerplexitySpecialist(),
            "codex": CodexSpecialist(),
            "cursor": CursorSpecialist(),
            "data_analytics": DataAnalyticsSpecialist(),
        }

    async def solve(self, p: Problem) -> Verdict:
        gov = self.authority.authorize(p, self.governance.evaluate(p))
        if gov.disposition == Disposition.BLOCK:
            v = Verdict(decision="BLOCKED", why="Governance policy blocks this request.",
                confidence=1.0, primary_risk="Policy violation", next_action="Do not execute.",
                governance=gov)
            v.decision_id = self.ledger.record(p, v)
            return v

        mapped = self.problem_engine.map(p)
        assignments = self.router.route(p, mapped)
        results = await asyncio.gather(*[self.providers[a.provider].run(a) for a in assignments]) if assignments else []
        claims = self.verifier.verify(results)

        payload = {
            "problem": p.model_dump(), "problem_map": mapped.model_dump(),
            "governance": gov.model_dump(),
            "specialists": [r.model_dump() for r in results],
            "prior_decisions": self.ledger.recent(5)
        }
        semantic = await self.judge.synthesize(payload)

        usable = [r for r in results if r.success]
        if semantic:
            v = Verdict(
                decision=str(semantic.get("decision","Insufficient evidence")),
                why=str(semantic.get("why","")),
                confidence=max(0.0,min(1.0,float(semantic.get("confidence",0.5)))),
                council_findings=list(semantic.get("council_findings") or []),
                critical_assumption=semantic.get("critical_assumption"),
                primary_risk=semantic.get("primary_risk"),
                evidence_gaps=list(semantic.get("evidence_gaps") or []),
                next_action=str(semantic.get("next_action","Obtain more evidence.")),
                governance=gov, claims=claims,
                providers_used=[r.provider for r in usable])
        else:
            # Honest deterministic fallback: it does not pretend to semantically adjudicate.
            gaps = [r.error for r in results if not r.success and r.error]
            if not usable:
                decision = "Insufficient evidence for a semantic verdict."
                why = "No semantic judge was available and no specialist returned usable evidence."
            else:
                decision = "Council evidence collected; semantic verdict pending."
                why = "Specialist results were collected, but the SARA semantic judge was unavailable. No fabricated synthesis was performed."
            v = Verdict(decision=decision, why=why, confidence=0.2 if usable else 0.05,
                council_findings=[f"{r.provider}: {'usable' if r.success else 'failed'}" for r in results],
                critical_assumption="A semantic judge must be configured for deliberative synthesis.",
                primary_risk="Mistaking collected provider output for a verified decision.",
                evidence_gaps=gaps, next_action="Configure OPENAI_API_KEY and rerun, or review evidence manually.",
                governance=gov, claims=claims, providers_used=[r.provider for r in usable])

        if gov.disposition == Disposition.ESCALATE:
            v.next_action = "Human approval required before execution. " + v.next_action
        v.decision_id = self.ledger.record(p, v)
        return v
