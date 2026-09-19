from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

@dataclass(frozen=True)
class CapabilityPassport:
    capability_id: str; version: str; dependencies: tuple[str,...]; permissions: tuple[str,...]; implementation_digest: str; issued_at: str
    @classmethod
    def create(cls,capability_id,version,dependencies,permissions):
        digest=sha256(json.dumps({"id":capability_id,"version":version,"dependencies":dependencies,"permissions":permissions},sort_keys=True).encode()).hexdigest()
        return cls(capability_id,version,tuple(dependencies),tuple(permissions),digest,datetime.now(timezone.utc).isoformat())
    def payload(self):
        return {"capability_id":self.capability_id,"version":self.version,"dependencies":list(self.dependencies),"permissions":list(self.permissions),"implementation_digest":self.implementation_digest,"issued_at":self.issued_at}
