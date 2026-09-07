from __future__ import annotations

import base64
import binascii
import hmac
import os
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


class SignerRequest(BaseModel):
    operation: Literal["sign", "verify"]
    algorithm: Literal["Ed25519", "ML-DSA"]
    key_id: str
    digest_b64: str
    signature_b64: str | None = None


class SignerEngine:
    def __init__(
        self,
        *,
        bearer_token: str,
        ed25519_key_id: str,
        ed25519_seed: bytes,
        ml_dsa_key_id: str,
        ml_dsa_seed: bytes,
    ) -> None:
        if not bearer_token:
            raise ValueError("bearer_token_required")
        if not ed25519_key_id or not ml_dsa_key_id:
            raise ValueError("key_id_required")
        if len(ed25519_seed) != 32 or len(ml_dsa_seed) != 32:
            raise ValueError("signer_seed_must_be_32_bytes")
        self._bearer_token = bearer_token
        self.ed25519_key_id = ed25519_key_id
        self.ml_dsa_key_id = ml_dsa_key_id
        self._ed25519_private = ed25519.Ed25519PrivateKey.from_private_bytes(ed25519_seed)
        self._ml_dsa_private = mldsa.MLDSA65PrivateKey.from_seed_bytes(ml_dsa_seed)

    @staticmethod
    def _seed_from_env(name: str) -> bytes:
        raw = os.getenv(name, "").strip()
        if not raw:
            raise ValueError(f"{name}_required")
        try:
            value = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"{name}_invalid_base64") from exc
        if len(value) != 32:
            raise ValueError(f"{name}_must_decode_to_32_bytes")
        return value

    @classmethod
    def from_env(cls) -> "SignerEngine":
        return cls(
            bearer_token=os.getenv("OMEGA_SIGNER_TOKEN", "").strip(),
            ed25519_key_id=os.getenv("OMEGA_ED25519_KEY_ID", "").strip(),
            ed25519_seed=cls._seed_from_env("OMEGA_ED25519_SEED_B64"),
            ml_dsa_key_id=os.getenv("OMEGA_ML_DSA_KEY_ID", "").strip(),
            ml_dsa_seed=cls._seed_from_env("OMEGA_ML_DSA_SEED_B64"),
        )

    def authorize(self, authorization: str | None) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="unauthorized")
        supplied = authorization[7:]
        if not hmac.compare_digest(supplied, self._bearer_token):
            raise HTTPException(status_code=401, detail="unauthorized")

    @staticmethod
    def decode_digest(value: str) -> bytes:
        try:
            digest = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="invalid_digest_b64") from None
        if len(digest) != 64:
            raise HTTPException(status_code=400, detail="digest_must_be_64_bytes")
        return digest

    @staticmethod
    def decode_signature(value: str | None) -> bytes:
        if not value:
            raise HTTPException(status_code=400, detail="signature_required")
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="invalid_signature_b64") from None

    def _validate_key_id(self, algorithm: str, key_id: str) -> None:
        expected = self.ed25519_key_id if algorithm == "Ed25519" else self.ml_dsa_key_id
        if key_id != expected:
            raise HTTPException(status_code=400, detail="key_id_mismatch")

    def sign(self, algorithm: str, key_id: str, digest: bytes) -> bytes:
        self._validate_key_id(algorithm, key_id)
        if algorithm == "Ed25519":
            return self._ed25519_private.sign(digest)
        return self._ml_dsa_private.sign(digest)

    def verify(self, algorithm: str, key_id: str, digest: bytes, signature: bytes) -> bool:
        self._validate_key_id(algorithm, key_id)
        try:
            if algorithm == "Ed25519":
                self._ed25519_private.public_key().verify(signature, digest)
            else:
                self._ml_dsa_private.public_key().verify(signature, digest)
            return True
        except InvalidSignature:
            return False


def create_app(engine: SignerEngine | None = None) -> FastAPI:
    app = FastAPI(title="SARA OMEGA Dual Signer", version="1.0.0")
    app.state.engine = engine

    def current_engine() -> SignerEngine:
        if app.state.engine is None:
            app.state.engine = SignerEngine.from_env()
        return app.state.engine

    @app.get("/health")
    def health() -> dict[str, object]:
        active = current_engine()
        return {
            "ok": True,
            "algorithms": ["Ed25519", "ML-DSA"],
            "key_ids": [active.ed25519_key_id, active.ml_dsa_key_id],
        }

    @app.post("/signer")
    def signer(request: SignerRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
        active = current_engine()
        active.authorize(authorization)
        digest = active.decode_digest(request.digest_b64)
        if request.operation == "sign":
            signature = active.sign(request.algorithm, request.key_id, digest)
            return {
                "algorithm": request.algorithm,
                "key_id": request.key_id,
                "signature_b64": base64.b64encode(signature).decode("ascii"),
            }

        signature = active.decode_signature(request.signature_b64)
        verified = active.verify(request.algorithm, request.key_id, digest, signature)
        return {
            "algorithm": request.algorithm,
            "key_id": request.key_id,
            "verified": verified,
        }

    return app


app = create_app()
