from __future__ import annotations
import json, re
from pathlib import Path
from .models import Disposition, GovernanceDecision, Problem

RISK_PATTERNS = {
    "credential": r"password|api[ _-]?key|secret token|credential",
    "pii": r"social security|ssn|passport|personal data|customer data",
    "illegal": r"break into|steal|fraud|illegal",
    "weapon": r"build (?:a )?(?:bomb|weapon)|explosive",
    "malware": r"ransomware|malware|credential stealer",
    "production_write": r"deploy to production|delete production|production database",
    "financial_high_impact": r"wire transfer|million dollars|acquisition|merger",
    "legal_commitment": r"sign contract|binding agreement|legal commitment",
    "personnel_action": r"fire employee|terminate employee"
}

class GovernanceEngine:
    def __init__(self, policy_file: str):
        self.policy_file = Path(policy_file)
        self.rules = json.loads(self.policy_file.read_text())["rules"]

    def detect_risks(self, problem: Problem) -> list[str]:
        text = " ".join([problem.query, problem.objective or "", problem.requested_action or ""]).lower()
        return sorted(tag for tag, pat in RISK_PATTERNS.items() if re.search(pat, text))

    def evaluate(self, problem: Problem) -> GovernanceDecision:
        tags = self.detect_risks(problem)
        matched, reasons = [], []
        disposition = Disposition.ALLOW
        rank = {Disposition.ALLOW: 0, Disposition.ESCALATE: 1, Disposition.BLOCK: 2}
        for rule in self.rules:
            if set(rule.get("risk_tags", [])) & set(tags):
                effect = Disposition(rule["effect"])
                matched.append(rule["id"])
                reasons.append(rule["reason"])
                if rank[effect] > rank[disposition]:
                    disposition = effect
        return GovernanceDecision(
            disposition=disposition, matched_rules=matched, reasons=reasons, risk_tags=tags
        )
