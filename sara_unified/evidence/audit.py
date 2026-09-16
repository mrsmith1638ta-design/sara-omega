from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    timestamp: str
    actor: str
    action: str
    details: dict[str, Any]
    previous_hash: str
    event_hash: str

class AuditLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    @staticmethod
    def _canonical(obj):
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _records(self):
        out=[]
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip(): out.append(json.loads(line))
        return out

    def append(self, actor, action, details):
        records = self._records()
        previous = records[-1]["event_hash"] if records else "GENESIS"
        body = {
            "sequence": len(records)+1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "details": details,
            "previous_hash": previous,
        }
        body["event_hash"] = hashlib.sha256(self._canonical(body).encode()).hexdigest()
        self.path.write_text(self.path.read_text(encoding="utf-8") + self._canonical(body) + "\n", encoding="utf-8")
        return AuditEvent(**body)

    def verify(self):
        previous="GENESIS"
        try: records=self._records()
        except Exception: return False
        for idx, record in enumerate(records, start=1):
            claimed=record.get("event_hash")
            body={k:v for k,v in record.items() if k!="event_hash"}
            expected=hashlib.sha256(self._canonical(body).encode()).hexdigest()
            if record.get("sequence") != idx or record.get("previous_hash") != previous or claimed != expected:
                return False
            previous=claimed
        return True
