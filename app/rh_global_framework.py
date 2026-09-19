from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .models import (
    Claim,
    CouncilChallenge,
    GovernanceDecision,
    Problem,
    ProblemMap,
    SpecialistResult,
    VerificationStatus,
)


FRAMEWORK_VERSION = "rh-global-reasoning-v1"

_RH_TOKENS = (
    "riemann",
    "zeta",
    "nyman",
    "beurling",
    "baez-duarte",
    "báez-duarte",
    "mobius",
    "möbius",
    "mertens",
    "tail attack",
)


def _bounded_strings(values: Iterable[Any], limit: int = 32) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            out.append(text[:1000])
        if len(out) >= limit:
            break
    return out


def _verification_bucket(status: VerificationStatus) -> str:
    if status == VerificationStatus.VERIFIED:
        return "PROVED_OR_VERIFIED"
    if status == VerificationStatus.CORROBORATED:
        return "CORROBORATED"
    if status == VerificationStatus.DISPUTED:
        return "DISPUTED"
    if status == VerificationStatus.STALE:
        return "STALE"
    if status == VerificationStatus.UNSUPPORTED:
        return "UNSUPPORTED"
    return "UNVERIFIABLE"


class RHGlobalReasoningFramework:
    """Apply the RH research discipline to every governed SARA request.

    This is a reasoning/governance framework, not a claim that every domain is
    literally a Riemann-Hypothesis problem. Literal RH equations are reserved
    for RH-relevant requests. The universal layer reuses the proof discipline:
    exact structure before inference, dependency tracking, cancellation/loss
    audits, explicit unknowns, adversarial shortcut rejection, and a certainty
    ceiling tied to evidence.
    """

    def initialize(self, problem: Problem, mapped: ProblemMap) -> dict[str, Any]:
        query_lower = problem.query.lower()
        literal_rh_math = any(token in query_lower for token in _RH_TOKENS)
        objective = mapped.objective or problem.objective or problem.query

        dependency_nodes = [
            {
                "id": f"subtask:{idx + 1}",
                "statement": text,
                "status": "OPEN",
            }
            for idx, text in enumerate(_bounded_strings(mapped.subtasks, 16))
        ]
        unknown_nodes = [
            {
                "id": f"unknown:{idx + 1}",
                "statement": text,
                "status": "UNRESOLVED",
            }
            for idx, text in enumerate(_bounded_strings(mapped.unknowns, 16))
        ]

        return {
            "framework": "RIEMANN_HYPOTHESIS_MATHEMATICAL_DISCIPLINE",
            "framework_version": FRAMEWORK_VERSION,
            "applied_to_every_request": True,
            "literal_rh_math": literal_rh_math,
            "literal_rh_equations_injected": literal_rh_math,
            "objective": str(objective)[:2000],
            "principles": [
                "Establish exact structure before estimating or generalizing.",
                "Separate verified facts, numerical/empirical evidence, hypotheses, and blocked claims.",
                "Expose assumptions and unresolved dependencies explicitly.",
                "Preserve signed/coupled terms long enough to test whether cancellation is being discarded.",
                "Audit lossy transformations such as absolute-value, worst-case, averaging, or finite-to-infinite promotion.",
                "Red-team hidden circularity and premises equivalent in strength to the desired conclusion.",
                "Do not promote finite evidence into a universal or asymptotic theorem.",
                "Cap conclusion strength at the strongest independently supported dependency.",
            ],
            "rh_analogy": {
                "exact_identity": "known facts / exact constraints",
                "candidate_lemma": "working hypothesis or proposed inference",
                "tail_or_discrepancy": "unresolved dependency or transfer error",
                "cancellation_audit": "check whether decomposition or bounding discarded useful interaction",
                "proof_gate": "conclusion-strength ceiling",
            },
            "problem_decomposition": {
                "facts": _bounded_strings(mapped.facts),
                "constraints": _bounded_strings(mapped.constraints),
                "assumptions": _bounded_strings(mapped.assumptions),
                "unknowns": _bounded_strings(mapped.unknowns),
                "risks": _bounded_strings(mapped.risks),
                "subtasks": _bounded_strings(mapped.subtasks),
            },
            "dependency_graph": {
                "objective": str(objective)[:2000],
                "subtasks": dependency_nodes,
                "unknowns": unknown_nodes,
                "all_required_dependencies_proved": False if unknown_nodes else None,
            },
            "loss_audit": {
                "preserve_cancellation": True,
                "independent_term_bounds_are_not_automatically_equivalent_to_original_expression": True,
                "finite_sample_is_not_global_limit": True,
                "status": "PENDING_EVIDENCE",
            },
            "promotion_gate": {
                "status": "ACTIVE",
                "rules": [
                    "No unsupported premise may be silently upgraded to fact.",
                    "No circular assumption may be used to prove the requested conclusion.",
                    "No finite observation may establish an infinite/universal claim without a transfer theorem.",
                    "No lossy bound may replace an exact coupled expression without recording the information loss.",
                    "Governance and authority controls always dominate this reasoning layer.",
                ],
            },
            "evidence_status": {
                "claims": [],
                "supported_claim_count": 0,
                "open_or_qualified_claim_count": 0,
            },
            "final_ceiling": {
                "status": "PENDING",
                "reason": "Evidence has not yet been synthesized.",
            },
        }

    def finalize_evidence(
        self,
        frame: dict[str, Any],
        *,
        claims: list[Claim],
        results: list[SpecialistResult],
        challenges: list[CouncilChallenge],
        science_analyses: list[dict[str, Any]],
        governance: GovernanceDecision,
    ) -> dict[str, Any]:
        out = deepcopy(frame)
        claim_rows: list[dict[str, Any]] = []
        supported = 0
        qualified = 0

        for claim in claims[:64]:
            bucket = _verification_bucket(claim.verification)
            if bucket in {"PROVED_OR_VERIFIED", "CORROBORATED"}:
                supported += 1
            else:
                qualified += 1
            claim_rows.append(
                {
                    "statement": claim.statement[:1500],
                    "provider": claim.provider[:128],
                    "verification": claim.verification.value,
                    "rh_framework_status": bucket,
                    "confidence": claim.confidence,
                    "contradiction_count": len(claim.contradictions),
                    "evidence_count": len(claim.evidence),
                }
            )

        failed_results = [
            {
                "provider": result.provider,
                "error": result.error,
            }
            for result in results[:32]
            if not result.success
        ]
        evidence_gaps = [
            challenge.finding[:1000]
            for challenge in challenges[:64]
            if challenge.evidence_gap
        ]

        unresolved = (
            qualified > 0
            or bool(evidence_gaps)
            or bool(failed_results)
            or governance.disposition.value != "ALLOW"
        )

        out["evidence_status"] = {
            "claims": claim_rows,
            "supported_claim_count": supported,
            "open_or_qualified_claim_count": qualified,
            "failed_specialists": failed_results,
            "evidence_gaps": evidence_gaps,
            "science_analysis_count": len(science_analyses),
        }
        out["dependency_graph"]["all_required_dependencies_proved"] = not unresolved
        out["loss_audit"]["status"] = "REVIEWED"
        out["loss_audit"]["challenge_count"] = len(challenges)
        out["promotion_gate"]["governance_disposition"] = governance.disposition.value

        if unresolved:
            out["final_ceiling"] = {
                "status": "QUALIFIED",
                "reason": (
                    "At least one dependency, evidence item, specialist result, "
                    "challenge, or governance condition remains unresolved."
                ),
            }
        else:
            out["final_ceiling"] = {
                "status": "SUPPORTED",
                "reason": "No unresolved dependency was detected in the available evidence record.",
            }
        return out

    def annotate_outcome(
        self,
        frame: dict[str, Any],
        *,
        decision: str,
        confidence: float,
        truth_gate: dict[str, Any],
        governance: GovernanceDecision,
    ) -> dict[str, Any]:
        out = deepcopy(frame)
        out["outcome"] = {
            "decision": str(decision)[:2000],
            "confidence": max(0.0, min(1.0, float(confidence))),
            "truth_gate_status": str(truth_gate.get("status", "NOT_APPLICABLE"))[:128],
            "truth_gate_allowed": truth_gate.get("allowed"),
            "governance_disposition": governance.disposition.value,
        }

        if governance.disposition.value != "ALLOW":
            out["final_ceiling"] = {
                "status": "GOVERNANCE_LIMITED",
                "reason": "Governance disposition limits promotion or execution.",
            }
        elif truth_gate.get("allowed") is False:
            out["final_ceiling"] = {
                "status": "TRUTH_GATE_LIMITED",
                "reason": str(truth_gate.get("reason") or "Truth gate rejected stronger synthesis.")[:1000],
            }
        return out
