from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from uuid import uuid4

class EpistemicStatus(str, Enum):
    VERIFIED="VERIFIED"; SUPPORTED="SUPPORTED"; INFERRED="INFERRED"; DISPUTED="DISPUTED"; UNVERIFIED="UNVERIFIED"; UNKNOWN="UNKNOWN"; CURRENTLY_INACCESSIBLE="CURRENTLY_INACCESSIBLE"

@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    source: str
    status: EpistemicStatus
    polarity: int
    timestamp: str
    evidence_digest: str
    @classmethod
    def create(cls, statement, source, status, polarity=1):
        ts=datetime.now(timezone.utc).isoformat()
        digest=sha256(f"{statement}|{source}|{ts}".encode()).hexdigest()
        return cls(str(uuid4()),statement,source,status,1 if polarity>=0 else -1,ts,digest)
