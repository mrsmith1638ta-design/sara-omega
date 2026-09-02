from .models import Disposition, GovernanceDecision, Problem


class AuthorityEngine:
    """Execution authority is separate from reasoning authority."""

    def authorize(self, problem: Problem, governance: GovernanceDecision) -> GovernanceDecision:
        if governance.disposition == Disposition.BLOCK:
            return governance
        if problem.requested_action and problem.authority_level < 3:
            return GovernanceDecision(
                disposition=Disposition.ESCALATE,
                matched_rules=governance.matched_rules,
                reasons=governance.reasons + ["Requested execution exceeds supplied authority level."],
                risk_tags=governance.risk_tags,
            )
        return governance
