from dataclasses import dataclass
from datetime import datetime, timezone
@dataclass(frozen=True)
class ChangeRecord:
    subject:str; before:object; after:object; reason:str; timestamp:str
class TemporalIntelligence:
    def compare(self,subject,before,after,reason="observed change"):
        return ChangeRecord(subject,before,after,reason,datetime.now(timezone.utc).isoformat())
