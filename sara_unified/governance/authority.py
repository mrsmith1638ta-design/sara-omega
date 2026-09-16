from sara_unified.contracts import AuthorityDecision
class AuthorityChain:
    def __init__(self,authorizer,policy,approvals): self.authorizer=authorizer; self.policy=policy; self.approvals=approvals
    def decide(self,ctx,permission,operation_class,approval_scope=None):
        granted=self.authorizer.allowed(ctx.roles,permission); decision=self.policy.evaluate(operation_class,granted)
        if not decision.allowed: return AuthorityDecision(False,decision.reason,"policy")
        if decision.approval_required and not (approval_scope and self.approvals.has(ctx.actor_id,approval_scope)): return AuthorityDecision(False,"required approval absent","approval")
        return AuthorityDecision(True,"authorized","authority-chain")
