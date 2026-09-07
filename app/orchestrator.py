from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

from .models import *
from .governance import GovernanceEngine
from .authority import AuthorityEngine
from .problem_engine import ProblemEngine
from .router import OmegaRouter
from .verification import EvidenceVerifier
from .memory import DecisionLedger
from .ledger import OmegaLedgerError, OmegaVerdictLedger
from .signing import DualSigner, SigningError
from .providers.perplexity import PerplexitySpecialist
from .providers.local_agents import CodexSpecialist, CursorSpecialist
from .providers.openai_judge import OpenAIJudge
from .providers.data_analytics import DataAnalyticsSpecialist
from .science.provider import ScienceSpecialist


class SaraOmega:
    def __init__(
        self,
        *,
        governance: Any | None = None,
        authority: Any | None = None,
        problem_engine: Any | None = None,
        router: Any | None = None,
        verifier: Any | None = None,
        history_ledger: Any | None = None,
        signed_ledger: Any | None = None,
        judge: Any | None = None,
        providers: dict[str, Any] | None = None,
    ):
        self.governance = governance or GovernanceEngine(os.getenv("SARA_POLICY_FILE", "./config/policies.json"))
        self.authority = authority or AuthorityEngine()
        self.problem_engine = problem_engine or ProblemEngine()
        self.router = router or OmegaRouter()
        self.verifier = verifier or EvidenceVerifier()
        self.history_ledger = history_ledger or DecisionLedger()
        self.judge = judge or OpenAIJudge()
        self.providers = providers or {
            "perplexity": PerplexitySpecialist(),
            "codex": CodexSpecialist(),
            "cursor": CursorSpecialist(),
            "data_analytics": DataAnalyticsSpecialist(),
            "science_ancient_egypt": ScienceSpecialist("science_ancient_egypt"),
            "science_classical_greek_roman": ScienceSpecialist("science_classical_greek_roman"),
            "science_engineering": ScienceSpecialist("science_engineering"),
            "science_maglev_ems": ScienceSpecialist("science_maglev_ems"),
            "science_maglev_eds": ScienceSpecialist("science_maglev_eds"),
            "science_maglev_hts": ScienceSpecialist("science_maglev_hts"),
        }
        self._signed_ledger_error: str | None = None
        if signed_ledger is not None:
            self.signed_ledger = signed_ledger
        else:
            try:
                signer = DualSigner.from_env()
                db = Path(os.getenv("SARA_DATA_DIR", "./data")).expanduser() / "sara_omega.db"
                self.signed_ledger = OmegaVerdictLedger(db, signer)
            except (SigningError, OmegaLedgerError, OSError) as exc:
                self.signed_ledger = None
                self._signed_ledger_error = type(exc).__name__

    @staticmethod
    def _complete(
        trace: CouncilTrace,
        stage: CouncilStage,
        *,
        status: str = "completed",
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        trace.completed.append(stage)
        trace.events.append(
            CouncilStageEvent(
                stage=stage,
                status=status,
                detail=detail[:512],
                metadata=(metadata or {}),
            )
        )

    async def _run_assignment(self, assignment: Assignment) -> SpecialistResult:
        provider = self.providers.get(assignment.provider)
        if provider is None:
            return SpecialistResult(
                provider=assignment.provider,
                role=assignment.role,
                task=assignment.task,
                success=False,
                error="provider_not_configured",
            )
        try:
            return await provider.run(assignment)
        except Exception as exc:
            return SpecialistResult(
                provider=assignment.provider,
                role=assignment.role,
                task=assignment.task,
                success=False,
                error=f"provider_failed:{type(exc).__name__}",
            )

    @staticmethod
    def _science_analyses(results: list[SpecialistResult]) -> list[dict[str, Any]]:
        analyses: list[dict[str, Any]] = []
        for result in results:
            payload = result.raw.get("science_analysis") if isinstance(result.raw, dict) else None
            if isinstance(payload, dict):
                bounded = dict(payload)
                bounded["execution_authority"] = False
                analyses.append(bounded)
        return analyses[:16]

    def _fallback_verdict(
        self,
        *,
        gov: GovernanceDecision,
        results: list[SpecialistResult],
        claims: list[Claim],
        challenges: list[CouncilChallenge],
    ) -> Verdict:
        usable = [r for r in results if r.success]
        gaps = [r.error for r in results if not r.success and r.error]
        if not usable:
            decision = "Insufficient evidence for a semantic verdict."
            why = "No semantic judge was available and no specialist returned usable evidence."
        else:
            decision = "Council evidence collected; semantic verdict pending."
            why = "Specialist results were collected, but the SARA semantic judge was unavailable. No fabricated synthesis was performed."
        return Verdict(
            decision=decision,
            why=why,
            confidence=0.2 if usable else 0.05,
            council_findings=[item.finding for item in challenges]
            + [f"{r.provider}: {'usable' if r.success else 'failed'}" for r in results],
            critical_assumption="A semantic judge must be configured for deliberative synthesis.",
            primary_risk="Mistaking collected provider output for a verified decision.",
            evidence_gaps=[str(gap) for gap in gaps],
            next_action="Obtain stronger evidence or review the Council record manually.",
            governance=gov,
            claims=claims,
            providers_used=[r.provider for r in usable],
            science_analyses=self._science_analyses(results),
        )

    async def solve(self, p: Problem) -> Verdict:
        trace = CouncilTrace()
        request_id = str(uuid.uuid4())

        self._complete(
            trace,
            CouncilStage.OBSERVE,
            metadata={"actor": p.actor, "authority_level": p.authority_level, "requested_action": bool(p.requested_action)},
        )

        mapped = self.problem_engine.map(p)
        self._complete(trace, CouncilStage.MAP, metadata={"unknown_count": len(mapped.unknowns)})

        preliminary_governance = self.governance.evaluate(p)
        self._complete(
            trace,
            CouncilStage.EVALUATE,
            metadata={
                "disposition": preliminary_governance.disposition.value,
                "risk_tags": preliminary_governance.risk_tags[:16],
            },
        )

        assignments = [] if preliminary_governance.disposition == Disposition.BLOCK else self.router.route(p, mapped)
        if assignments:
            results = await asyncio.gather(*[self._run_assignment(a) for a in assignments])
            generate_status = "completed"
            generate_detail = "Relevant specialists invoked."
        else:
            results = []
            generate_status = "policy_suppressed" if preliminary_governance.disposition == Disposition.BLOCK else "completed_no_external_specialists"
            generate_detail = "External specialist execution suppressed by governance." if preliminary_governance.disposition == Disposition.BLOCK else "No external specialist was relevant."
        science_analyses = self._science_analyses(results)
        self._complete(
            trace,
            CouncilStage.GENERATE,
            status=generate_status,
            detail=generate_detail,
            metadata={
                "assignments": [a.provider for a in assignments],
                "science_domains": [item.get("domain") for item in science_analyses if item.get("domain")],
            },
        )

        claims = self.verifier.verify(results)
        cross_findings = self.verifier.cross_examine(results, claims)
        self._complete(
            trace,
            CouncilStage.CROSS_EXAMINE,
            metadata={"findings": len(cross_findings), "claims": len(claims)},
        )

        stress_findings = self.verifier.stress_test(claims, cross_findings)
        challenges = [*cross_findings, *stress_findings]
        self._complete(
            trace,
            CouncilStage.STRESS_TEST,
            metadata={"findings": len(stress_findings)},
        )

        if preliminary_governance.disposition == Disposition.BLOCK:
            semantic = {
                "decision": "BLOCKED",
                "why": "Governance policy blocks this request.",
                "confidence": 1.0,
                "council_findings": [item.finding for item in challenges],
                "critical_assumption": None,
                "primary_risk": "Policy violation",
                "evidence_gaps": [],
                "next_action": "Do not execute the requested action.",
            }
            synth_status = "policy_blocked_synthesis"
        else:
            judge_payload = {
                "problem": p.model_dump(),
                "problem_map": mapped.model_dump(),
                "assignments": [a.model_dump() for a in assignments],
                "specialists": [r.model_dump() for r in results],
                "science_analyses": science_analyses,
                "science_governance": {
                    "rule": "Science outputs are advisory evidence only; preserve provenance classes and never promote reconstruction or consensus to verified fact.",
                    "execution_authority": False,
                },
                "claims": [c.model_dump() for c in claims],
                "cross_examination": [item.model_dump() for item in cross_findings],
                "stress_test": [item.model_dump() for item in stress_findings],
                "governance": preliminary_governance.model_dump(),
                "prior_decisions": self.history_ledger.recent(5),
            }
            semantic = await self.judge.synthesize(judge_payload)
            synth_status = "completed" if semantic else "judge_unavailable"
        self._complete(trace, CouncilStage.SYNTHESIZE, status=synth_status)

        final_governance = self.authority.authorize(p, preliminary_governance)
        self._complete(
            trace,
            CouncilStage.GOVERN,
            metadata={"disposition": final_governance.disposition.value},
        )

        usable = [r for r in results if r.success]
        if semantic:
            confidence = max(0.0, min(1.0, float(semantic.get("confidence", 0.5))))
            ceilings = [item.confidence_ceiling for item in stress_findings if item.confidence_ceiling is not None]
            if ceilings:
                confidence = min(confidence, min(ceilings))
            verdict = Verdict(
                decision=str(semantic.get("decision", "Insufficient evidence")),
                why=str(semantic.get("why", "")),
                confidence=confidence,
                council_findings=list(semantic.get("council_findings") or []) + [item.finding for item in challenges],
                critical_assumption=semantic.get("critical_assumption"),
                primary_risk=semantic.get("primary_risk"),
                evidence_gaps=list(semantic.get("evidence_gaps") or []) + [item.finding for item in challenges if item.evidence_gap],
                next_action=str(semantic.get("next_action", "Obtain more evidence.")),
                governance=final_governance,
                claims=claims,
                providers_used=[r.provider for r in usable],
                science_analyses=science_analyses,
            )
        else:
            verdict = self._fallback_verdict(
                gov=final_governance,
                results=results,
                claims=claims,
                challenges=challenges,
            )

        if final_governance.disposition == Disposition.ESCALATE:
            verdict.next_action = "Human approval required before any execution. " + verdict.next_action
        verdict.request_id = request_id
        self._complete(trace, CouncilStage.VERDICT)

        self._complete(trace, CouncilStage.RECORD, status="attempted")
        verdict.council_trace = trace
        durable_id = str(uuid.uuid4())
        ledger_payload = {
            "request_id": request_id,
            "problem": p.model_dump(),
            "problem_map": mapped.model_dump(),
            "assignments": [a.model_dump() for a in assignments],
            "specialist_results": [r.model_dump() for r in results],
            "science_analyses": science_analyses,
            "challenges": [item.model_dump() for item in challenges],
            "verdict": verdict.model_dump(exclude={"decision_id", "integrity"}),
        }
        if self.signed_ledger is None:
            verdict.integrity = IntegrityStatus(
                status="NON_DURABLE_SIGNER_UNAVAILABLE",
                error=self._signed_ledger_error or "dual_signer_not_configured",
            )
            verdict.decision_id = None
            trace.events[-1].status = "non_durable"
            trace.events[-1].detail = "Signed ledger unavailable; reasoning result was not durably accepted."
            return verdict
        try:
            integrity = await self.signed_ledger.append(
                durable_id,
                ledger_payload,
                supersedes_decision_id=verdict.supersedes_decision_id,
            )
        except OmegaLedgerError as exc:
            verdict.integrity = IntegrityStatus(
                status="NON_DURABLE_RECORD_FAILED",
                error=str(exc)[:512],
            )
            verdict.decision_id = None
            trace.events[-1].status = "non_durable"
            trace.events[-1].detail = "Signed ledger acceptance failed closed."
            return verdict

        verdict.integrity = integrity
        verdict.decision_id = durable_id
        trace.events[-1].status = "durable"
        trace.events[-1].detail = "Dual-signed append and read-after-write confirmation succeeded."
        return verdict
