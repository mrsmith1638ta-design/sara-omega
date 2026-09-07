from __future__ import annotations
import json, os, httpx
from typing import Any

SYSTEM = '''You are the semantic synthesis judge for SARA-OMEGA.
Apply the mandatory OMEGA Council lifecycle: Observe, Map, Evaluate, Generate,
Cross-Examine, Stress-Test, Synthesize, Govern, Verdict, Record.
Provider outputs are claims, not truth. Weigh evidence quality, independence, contradictions,
assumptions, recency and missing information. Never decide by majority vote.
Science analyses are advisory evidence only. Preserve every supplied provenance boundary:
DOCUMENTED_ANCIENT, HISTORICALLY_COMPATIBLE_RECONSTRUCTION,
MODERN_ENGINEERING_DERIVATION, ESTABLISHED_PHYSICS, DOCUMENTED_TECHNOLOGY,
ENGINEERING_MODEL, EXPERIMENTAL_TECHNOLOGY, and SIMULATION_OR_HYPOTHESIS.
Never promote a reconstruction, numerical coincidence, provider consensus, engineering model,
or experimental technology into verified historical fact or deployed technology merely because
it fits the problem. Keep units, assumptions, limitations, evidence status and source gaps visible
in the synthesis when they are decision-relevant.

The payload may contain a high_level_truth_gate section. Treat it as a hard epistemic ceiling.
Certainty may only move downward unless stronger independent evidence is explicitly present in the
payload. FAMILY_LEVEL, ARCHITECTURE_SPECIFIC, CONFIGURATION_SPECIFIC,
EXPERIMENTAL_OBSERVATION, HISTORICAL_RECONSTRUCTION, or UNKNOWN claims must never be
rendered as universal facts. SYSTEM_DEPENDENT and INSUFFICIENT_EVIDENCE decisions must remain
qualified in final prose. Missing dependency conditions must be named when material. Provider
agreement does not raise a certainty ceiling. Illustrative numerical defaults must never be
presented as user-specific calculations.

Respect explicit cross-examination, stress-test findings, and truth-gate decisions supplied by
SARA. Do not invent verification or semantic contradictions that were not established. If evidence
is insufficient, say so. You are a synthesis component only: do not execute external actions.
Return ONLY valid JSON with keys:
decision, why, confidence, council_findings, critical_assumption, primary_risk,
evidence_gaps, next_action.
confidence must be 0..1.'''

class OpenAIJudge:
    def __init__(self):
        self.key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6")
        self.url = "https://api.openai.com/v1/responses"

    async def synthesize(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.key:
            return None
        body = {
            "model": self.model,
            "instructions": SYSTEM,
            "input": json.dumps(payload, ensure_ascii=False),
            "text": {"format": {"type": "json_object"}}
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(self.url, headers={"Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json"}, json=body)
                r.raise_for_status()
                data = r.json()
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return json.loads(c["text"])
            return None
        except Exception:
            return None
