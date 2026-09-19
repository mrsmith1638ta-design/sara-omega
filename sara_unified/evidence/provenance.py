from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

@dataclass(frozen=True)
class ProvenanceRecord:
    record_id: str
    subject: str
    source: str
    digest: str
    recorded_at: str

class ProvenanceRegistry:
    def __init__(self): self._records={}
    def record(self, subject: str, content: bytes, source: str):
        if not subject or not source: raise ValueError("subject and source required")
        rec=ProvenanceRecord(str(uuid4()),subject,source,sha256(content).hexdigest(),datetime.now(timezone.utc).isoformat())
        self._records[rec.record_id]=rec; return rec
    def verify(self, record_id: str, content: bytes):
        rec=self._records.get(record_id)
        return bool(rec) and rec.digest == sha256(content).hexdigest()
