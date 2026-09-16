from dataclasses import dataclass
from sara_unified.errors import GovernanceUnavailableError
@dataclass(frozen=True)
class SIOSDecision:
    allowed:bool; decision_id:str; reason:str
class SIOSGate:
    def __init__(self,mandatory=False,decision_provider=None): self.mandatory=mandatory; self.decision_provider=decision_provider
    def authorize(self,request):
        if not self.decision_provider:
            if self.mandatory: raise GovernanceUnavailableError("SIOS unavailable")
            return SIOSDecision(False,"none","SIOS not configured")
        return self.decision_provider(request)
