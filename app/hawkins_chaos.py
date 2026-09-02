from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field


DecisionName = Literal["ALLOW", "REVIEW", "BLOCK"]


class HawkinsChaosRequest(BaseModel):
    state: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    action: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    perturbations: int = Field(default=13, ge=3, le=101)
    epsilon: float = Field(default=0.05, gt=0.0, le=0.5)


class HawkinsChaosEngine:
    """Nonlinear decision-state stability analysis for SARA.

    This layer estimates trajectory stability. It does not authorize actions,
    override evidence, or convert unsupported claims into truth.
    """

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-hawkins-chaos-dynamics",
            "framework": "Hawkins Chaos",
            "mathematical_role": "nonlinear self-stability and trajectory analysis",
            "capabilities": [
                "perturbation_testing",
                "attractor_detection",
                "bifurcation_detection",
                "lyapunov_style_stability_scoring",
                "entropy_complexity_tracking",
                "effective_confidence_adjustment",
            ],
            "boundary": "advisory_only_never_overrides_truth_authorization_or_failsafe",
        }

    def analyze(self, request: HawkinsChaosRequest) -> dict[str, Any]:
        base = self._base_vector(request)
        trajectory = self._trajectory(base, request)
        decisions = [point["decision"] for point in trajectory]
        scores = [point["score"] for point in trajectory]
        base_decision = self._decision(base["score"])
        flips = sum(1 for decision in decisions if decision != base_decision)
        counts = Counter(decisions)

        entropy = self._entropy(counts, len(decisions))
        attractor_strength = max(counts.values()) / len(decisions)
        perturbation_resilience = 1.0 - flips / len(decisions)
        bifurcation_risk = flips / len(decisions)
        spread = max(scores) - min(scores)
        lyapunov_estimate = math.log1p(spread / max(request.epsilon, 1e-9))
        divergence_score = self._clamp(lyapunov_estimate / 3.0)
        convergence = 1.0 - self._clamp(self._stddev(scores) * 2.0)
        chaos_stability = self._clamp(
            (
                perturbation_resilience
                + attractor_strength
                + convergence
                + (1.0 - bifurcation_risk)
                + (1.0 - divergence_score)
            )
            / 5.0
        )
        base_confidence = base["confidence"]
        effective_confidence = self._clamp(base_confidence * chaos_stability)

        return {
            "service": "sara-hawkins-chaos-dynamics",
            "policy": "stability_adjustment_only",
            "base_decision": base_decision,
            "base_confidence": round(base_confidence, 6),
            "effective_confidence": round(effective_confidence, 6),
            "effective_authority": self._effective_authority(
                base_decision,
                effective_confidence,
                chaos_stability,
                bifurcation_risk,
            ),
            "hawkins_chaos": {
                "lambda_estimate": round(lyapunov_estimate, 6),
                "entropy": round(entropy, 6),
                "bifurcation_risk": round(bifurcation_risk, 6),
                "attractor_strength": round(attractor_strength, 6),
                "perturbation_resilience": round(perturbation_resilience, 6),
                "divergence_score": round(divergence_score, 6),
                "convergence": round(convergence, 6),
                "stability_multiplier": round(chaos_stability, 6),
            },
            "trajectory": trajectory,
            "state_vector": {
                "confidence": round(base["confidence"], 6),
                "support": round(base["support"], 6),
                "contradiction": round(base["contradiction"], 6),
                "uncertainty": round(base["uncertainty"], 6),
                "risk": round(base["risk"], 6),
                "context_density": round(base["context_density"], 6),
                "action_pressure": round(base["action_pressure"], 6),
            },
            "boundary": "Hawkins Chaos may downgrade authority for instability; it never upgrades unsupported truth.",
        }

    def analyze_verdict(self, verdict: Any, *, query: str = "", context: dict[str, Any] | None = None) -> dict[str, Any]:
        data = verdict.model_dump() if hasattr(verdict, "model_dump") else dict(verdict)
        evidence = []
        for claim in data.get("claims", []) or []:
            if hasattr(claim, "model_dump"):
                claim = claim.model_dump()
            evidence.append(
                {
                    "status": claim.get("verification", "unverifiable"),
                    "confidence": claim.get("confidence", 0.5),
                    "contradictions": claim.get("contradictions", []),
                    "evidence": claim.get("evidence", []),
                }
            )
        governance = data.get("governance") or {}
        if hasattr(governance, "model_dump"):
            governance = governance.model_dump()
        state = {
            "query": query,
            "decision": data.get("decision", ""),
            "confidence": data.get("confidence", 0.5),
            "evidence_gaps": data.get("evidence_gaps", []),
            "primary_risk": data.get("primary_risk"),
            "governance": governance,
            "context": context or {},
        }
        return self.analyze(HawkinsChaosRequest(state=state, evidence=evidence))

    def _base_vector(self, request: HawkinsChaosRequest) -> dict[str, float]:
        state = request.state
        evidence = request.evidence
        confidence = self._number(state.get("confidence", state.get("epistemic_confidence", 0.5)), 0.5)
        statuses = [str(item.get("status", item.get("verdict", ""))).lower() for item in evidence]
        support = self._ratio(statuses, {"verified", "corroborated", "supported", "allow", "true"})
        contradiction = self._ratio(statuses, {"disputed", "contradicted", "block", "false"})
        if evidence:
            uncertainty = self._ratio(statuses, {"unsupported", "stale", "unverifiable", "unavailable", "unknown", ""})
        else:
            uncertainty = 0.45 if not state.get("evidence_gaps") else 0.65

        governance = state.get("governance") if isinstance(state.get("governance"), dict) else {}
        risk_tags = governance.get("risk_tags", []) if isinstance(governance, dict) else []
        risk_text = " ".join(
            str(value)
            for value in [
                state.get("primary_risk", ""),
                state.get("risk", ""),
                *list(risk_tags or []),
            ]
        ).lower()
        risk = self._clamp(0.12 * len(risk_tags or []) + (0.35 if risk_text.strip() else 0.0))
        if re.search(r"block|danger|violation|contradict|unsupported|production|secret|credential", risk_text):
            risk = self._clamp(risk + 0.25)

        context = state.get("context") if isinstance(state.get("context"), dict) else {}
        context_density = self._clamp(min(len(str(context)) / 1200.0, 1.0))
        action = request.action or {}
        action_pressure = 0.0
        if state.get("requested_action") or action:
            action_pressure += 0.35
        action_text = f"{action} {state.get('requested_action', '')}".lower()
        if re.search(r"deploy|delete|execute|approve|promote|production", action_text):
            action_pressure += 0.3

        score = self._score(
            confidence=confidence,
            support=support,
            contradiction=contradiction,
            uncertainty=uncertainty,
            risk=risk,
            context_density=context_density,
            action_pressure=action_pressure,
        )
        return {
            "confidence": self._clamp(confidence),
            "support": support,
            "contradiction": contradiction,
            "uncertainty": uncertainty,
            "risk": risk,
            "context_density": context_density,
            "action_pressure": self._clamp(action_pressure),
            "score": score,
        }

    def _trajectory(self, base: dict[str, float], request: HawkinsChaosRequest) -> list[dict[str, Any]]:
        dimensions = ["confidence", "support", "contradiction", "uncertainty", "risk", "context_density", "action_pressure"]
        trajectory = []
        count = int(request.perturbations)
        for index in range(count):
            vector = dict(base)
            seed = self._seed(request, index)
            for dim_index, dimension in enumerate(dimensions):
                offset = self._deterministic_offset(seed, dim_index) * request.epsilon
                vector[dimension] = self._clamp(vector[dimension] + offset)
            score = self._score(**{key: vector[key] for key in dimensions})
            trajectory.append(
                {
                    "step": index,
                    "score": round(score, 6),
                    "decision": self._decision(score),
                    "delta": round(score - base["score"], 6),
                }
            )
        return trajectory

    def _score(
        self,
        *,
        confidence: float,
        support: float,
        contradiction: float,
        uncertainty: float,
        risk: float,
        context_density: float,
        action_pressure: float,
    ) -> float:
        raw = (
            0.46 * confidence
            + 0.24 * support
            + 0.08 * context_density
            - 0.42 * contradiction
            - 0.23 * uncertainty
            - 0.19 * risk
            - 0.12 * action_pressure
        )
        return self._clamp(raw)

    def _decision(self, score: float) -> DecisionName:
        if score >= 0.62:
            return "ALLOW"
        if score >= 0.38:
            return "REVIEW"
        return "BLOCK"

    def _effective_authority(
        self,
        base_decision: DecisionName,
        effective_confidence: float,
        stability: float,
        bifurcation_risk: float,
    ) -> str:
        if base_decision == "BLOCK":
            return "LOW"
        if effective_confidence >= 0.78 and stability >= 0.8 and bifurcation_risk <= 0.1:
            return "HIGH"
        if effective_confidence >= 0.45 and stability >= 0.55 and bifurcation_risk <= 0.35:
            return "MEDIUM"
        return "LOW"

    def _seed(self, request: HawkinsChaosRequest, index: int) -> str:
        payload = {
            "state": request.state,
            "evidence": request.evidence,
            "action": request.action,
            "parameters": request.parameters,
            "index": index,
        }
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()

    def _deterministic_offset(self, seed: str, dim_index: int) -> float:
        start = (dim_index * 4) % max(len(seed) - 4, 1)
        value = int(seed[start : start + 4], 16) / 0xFFFF
        return (value * 2.0) - 1.0

    def _entropy(self, counts: Counter, total: int) -> float:
        if total <= 1:
            return 0.0
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return self._clamp(entropy / math.log2(3))

    def _stddev(self, values: list[float]) -> float:
        if len(values) <= 1:
            return 0.0
        avg = sum(values) / len(values)
        variance = sum((value - avg) ** 2 for value in values) / len(values)
        return math.sqrt(variance)

    def _ratio(self, statuses: list[str], positive: set[str]) -> float:
        if not statuses:
            return 0.0
        return sum(1 for status in statuses if status in positive) / len(statuses)

    def _number(self, value: Any, default: float) -> float:
        try:
            return self._clamp(float(value))
        except (TypeError, ValueError):
            return default

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))
