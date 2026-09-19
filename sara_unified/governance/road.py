from dataclasses import dataclass
from sara_unified.errors import GovernanceUnavailableError
@dataclass(frozen=True)
class RoadStatus:
    reachable:bool; trusted:bool; production_accepted:bool; evidence_state:str
class RoadGate:
    def __init__(self,mandatory=False,status_provider=None): self.mandatory=mandatory; self.status_provider=status_provider
    def status(self):
        if not self.status_provider:
            if self.mandatory: raise GovernanceUnavailableError("ROAD status unavailable")
            return RoadStatus(False,False,False,"UNVERIFIED")
        return self.status_provider()
