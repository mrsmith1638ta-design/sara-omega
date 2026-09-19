from dataclasses import dataclass
import base64, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

@dataclass(frozen=True)
class SignedPayload:
    signature_b64: str

class Ed25519Signer:
    def __init__(self, private_key=None, public_key=None): self.private_key=private_key; self.public_key=public_key or (private_key.public_key() if private_key else None)
    @classmethod
    def generate(cls): return cls(private_key=Ed25519PrivateKey.generate())
    @staticmethod
    def canonical(payload): return json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    def sign_json(self,payload):
        if not self.private_key: raise ValueError("private key unavailable")
        return SignedPayload(base64.b64encode(self.private_key.sign(self.canonical(payload))).decode())
    def verify_json(self,payload,signature_b64):
        try:
            self.public_key.verify(base64.b64decode(signature_b64), self.canonical(payload)); return True
        except (InvalidSignature, ValueError, TypeError): return False
