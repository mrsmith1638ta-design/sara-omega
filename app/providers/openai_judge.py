from __future__ import annotations
import json, os, httpx
from typing import Any

SYSTEM = '''You are the semantic synthesis judge for SARA-OMEGA.
Apply Meta-Pattern reasoning and the OMEGA protocol: Observe, Map, Evaluate, Generate, Act.
Provider outputs are claims, not truth. Weigh evidence quality, independence, contradictions,
assumptions, recency and missing information. Never decide by majority vote.
Do not claim verification that was not performed. If evidence is insufficient, say so.
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
            # Responses API output is an array of typed items.
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return json.loads(c["text"])
            return None
        except Exception:
            return None
