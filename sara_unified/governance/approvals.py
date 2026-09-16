from dataclasses import dataclass
from datetime import datetime, timezone
@dataclass(frozen=True)
class Approval:
    subject:str; approver:str; scope:str; approved_at:str
class ApprovalStore:
    def __init__(self): self._items={}
    def grant(self,subject,approver,scope): self._items[(subject,scope)] = Approval(subject,approver,scope,datetime.now(timezone.utc).isoformat()); return self._items[(subject,scope)]
    def has(self,subject,scope): return (subject,scope) in self._items
