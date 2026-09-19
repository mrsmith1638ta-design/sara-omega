import hmac, hashlib, time
from dataclasses import dataclass
from sara_unified.errors import AuthenticationError

@dataclass(frozen=True)
class Identity:
    actor_id: str
    roles: frozenset[str]

class HMACIdentityVerifier:
    def __init__(self, secrets): self.secrets=dict(secrets)
    def sign(self, actor_id, payload: bytes):
        secret=self.secrets[actor_id].encode() if isinstance(self.secrets[actor_id], str) else self.secrets[actor_id]
        return hmac.new(secret,payload,hashlib.sha256).hexdigest()
    def verify(self, actor_id, payload: bytes, signature: str, roles=()):
        if actor_id not in self.secrets: raise AuthenticationError("unknown actor")
        if not hmac.compare_digest(self.sign(actor_id,payload), signature): raise AuthenticationError("invalid signature")
        return Identity(actor_id, frozenset(roles))
