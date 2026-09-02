from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "i", "in", "is", "it", "not", "of", "on", "or", "that",
    "the", "this", "to", "was", "we", "with", "you", "your",
}


class ConcentrationRequest(BaseModel):
    objective: str = Field(min_length=1)
    output: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    threshold: float = Field(default=0.72, ge=0.0, le=1.0)


class ConcentrationGovernor:
    """Objective-lock formula for reducing AI deviation.

    The governor scores whether the produced reasoning remains concentrated on
    the user's stated objective. It is deterministic and advisory/fail-closed:
    low focus requires refocus before the answer should be treated as final.
    """

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-concentration-governor",
            "formula": "F = 1 - D; D = .34(1-A)+.18S+.16E+.16M+.16R",
            "capabilities": [
                "objective_lock",
                "scope_drift_detection",
                "semantic_focus_scoring",
                "constraint_coverage",
                "refocus_mandate",
            ],
            "boundary": "does_not_override_truth_authorization_runtime_assurance_or_failsafe",
        }

    def analyze(self, request: ConcentrationRequest) -> dict[str, Any]:
        objective_tokens = self._tokens(request.objective)
        output_tokens = self._tokens(request.output)
        constraint_tokens = self._tokens(" ".join(request.constraints))
        context_tokens = self._tokens(str(request.context))

        alignment = self._coverage(objective_tokens, output_tokens)
        constraint_coverage = self._coverage(constraint_tokens, output_tokens) if constraint_tokens else 1.0
        scope_drift = self._scope_drift(output_tokens, objective_tokens | constraint_tokens | context_tokens)
        entropy = self._normalized_entropy(output_tokens)
        action_mismatch = self._action_mismatch(request.objective, request.output)
        risk_pressure = self._risk_pressure(request.output, request.context)

        deviation_score = self._clamp(
            0.34 * (1.0 - alignment)
            + 0.18 * scope_drift
            + 0.16 * entropy
            + 0.16 * action_mismatch
            + 0.16 * risk_pressure
            + 0.12 * (1.0 - constraint_coverage)
        )
        focus_score = self._clamp(1.0 - deviation_score)
        refocus_required = focus_score < request.threshold

        return {
            "service": "sara-concentration-governor",
            "policy": "objective_lock_deviation_control",
            "formula": {
                "focus_score": "F = 1 - D",
                "deviation_score": "D = .34(1-A)+.18S+.16E+.16M+.16R+.12(1-K)",
                "A": "objective_alignment",
                "S": "scope_drift",
                "E": "output_entropy",
                "M": "action_mismatch",
                "R": "risk_pressure",
                "K": "constraint_coverage",
            },
            "focus_score": round(focus_score, 6),
            "deviation_score": round(deviation_score, 6),
            "threshold": request.threshold,
            "refocus_required": refocus_required,
            "render_instruction": "refocus_before_final" if refocus_required else "render",
            "components": {
                "objective_alignment": round(alignment, 6),
                "constraint_coverage": round(constraint_coverage, 6),
                "scope_drift": round(scope_drift, 6),
                "entropy": round(entropy, 6),
                "action_mismatch": round(action_mismatch, 6),
                "risk_pressure": round(risk_pressure, 6),
            },
            "refocus_prompt": self._refocus_prompt(request) if refocus_required else "",
            "boundary": "Low concentration can force refocus, but cannot approve false, unsafe, or unauthorized content.",
        }

    def analyze_verdict(self, *, objective: str, verdict: Any, context: dict[str, Any] | None = None) -> dict[str, Any]:
        data = verdict.model_dump() if hasattr(verdict, "model_dump") else dict(verdict)
        output = " ".join(
            str(value)
            for value in [
                data.get("decision", ""),
                data.get("why", ""),
                data.get("critical_assumption", ""),
                data.get("primary_risk", ""),
                data.get("next_action", ""),
            ]
            if value
        )
        constraints = [
            "highest level of reasoning",
            "problem solving",
            "stay on the user's objective",
            "avoid deviation",
        ]
        return self.analyze(
            ConcentrationRequest(
                objective=objective,
                output=output or "No verdict output was produced.",
                constraints=constraints,
                context=context or {},
            )
        )

    def _tokens(self, text: str) -> set[str]:
        raw = text.lower()
        tokens = {
            self._stem(token)
            for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", raw)
            if token not in STOPWORDS
        }
        if "objective lock" in raw or "concentration" in tokens or "focus" in tokens:
            tokens.update({"objective", "lock", "focus", "concentration", "prevent", "deviation"})
        if "code" in tokens:
            tokens.update({"program", "programming", "engineering"})
        if "test" in tokens:
            tokens.add("verify")
        if "verify" in tokens:
            tokens.add("test")
        if "formula" in tokens:
            tokens.add("equation")
        return tokens

    def _stem(self, token: str) -> str:
        for suffix in ("ing", "tion", "ed", "es", "s"):
            if token.endswith(suffix) and len(token) > len(suffix) + 3:
                return token[: -len(suffix)]
        return token

    def _coverage(self, required: set[str], observed: set[str]) -> float:
        if not required:
            return 1.0
        return len(required & observed) / len(required)

    def _scope_drift(self, output: set[str], allowed: set[str]) -> float:
        if not output:
            return 1.0
        if not allowed:
            return 0.5
        outside = output - allowed
        raw = len(outside) / len(output)
        return self._clamp(max(0.0, raw - 0.35) / 0.65)

    def _normalized_entropy(self, tokens: set[str]) -> float:
        if len(tokens) <= 1:
            return 0.0
        counts = Counter(tokens)
        total = sum(counts.values())
        entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
        volume_factor = min(len(tokens) / 80.0, 1.0)
        return self._clamp((entropy / math.log2(max(len(counts), 2))) * volume_factor)

    def _action_mismatch(self, objective: str, output: str) -> float:
        objective_actions = self._action_words(objective)
        if not objective_actions:
            return 0.0
        output_actions = self._action_words(output)
        return 1.0 - self._coverage(objective_actions, output_actions)

    def _action_words(self, text: str) -> set[str]:
        verbs = {
            "add", "analyze", "build", "check", "code", "deploy", "diagnose",
            "fix", "integrate", "plan", "prevent", "protect", "reason", "solve",
            "test", "verify",
        }
        tokens = self._tokens(text)
        return tokens & verbs

    def _risk_pressure(self, output: str, context: dict[str, Any]) -> float:
        text = f"{output} {context}".lower()
        pressure = 0.0
        if re.search(r"\b(?:maybe|probably|guess|unclear|unknown|unsupported)\b", text):
            pressure += 0.22
        if re.search(r"\b(?:secret|credential|delete|destructive|production|unsafe|bypass)\b", text):
            pressure += 0.28
        if re.search(r"\b(?:metaphor|story|philosophy|brand)\b", text):
            pressure += 0.18
        return self._clamp(pressure)

    def _refocus_prompt(self, request: ConcentrationRequest) -> str:
        return (
            "Refocus on the objective only. State the concrete engineering action, "
            "the governing constraint, and the verification step. Remove unrelated "
            "narrative, speculation, and unsupported claims."
        )

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))
