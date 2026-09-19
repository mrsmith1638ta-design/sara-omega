from dataclasses import dataclass
@dataclass(frozen=True)
class PolicyDecision:
    allowed:bool; approval_required:bool; reason:str
class PolicyEngine:
    def evaluate(self,operation_class,permission_granted):
        if not permission_granted: return PolicyDecision(False,False,"permission denied")
        value=getattr(operation_class,"value",operation_class)
        if value=="DESTRUCTIVE": return PolicyDecision(False,True,"destructive operations require explicit approval policy")
        if value in {"STATE_CHANGING","SENSITIVE"}: return PolicyDecision(True,True,"approval required")
        return PolicyDecision(True,False,"read-only allowed")
