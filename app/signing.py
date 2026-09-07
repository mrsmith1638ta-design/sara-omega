from __future__ import annotations

import base64
import os
from typing import Protocol

import httpx

from .models import SignatureRecord


class SigningError(RuntimeError):
    pass


class Signer(Protocol):
    algorithm: str

    async def sign(self, digest: bytes) -> SignatureRecord: ...

    async def verify(self, digest: bytes, signature: SignatureRecord) -> bool: ...


class ExternalHttpSigner:
    def __init__(
        self,
        *,
        algorithm: str,
        url: str,
        key_id: str,
        token: str,
        timeout_seconds: float = 15.0,
    ):
        self.algorithm = algorithm
        self.url = url.rstrip("/")
        self.key_id = key_id
        self._token = token
        self.timeout_seconds = timeout_seconds
        if not self.url or not self.key_id or not self._token:
            raise SigningError("signer_configuration_incomplete")

    def __repr__(self) -> str:
        return f"ExternalHttpSigner(algorithm={self.algorithm!r}, url={self.url!r}, key_id={self.key_id!r})"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def sign(self, digest: bytes) -> SignatureRecord:
        payload = {
            "operation": "sign",
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "digest_b64": base64.b64encode(digest).decode("ascii"),
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.url, headers=self._headers(), json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise SigningError(f"signer_request_failed:{type(exc).__name__}") from None
        signature_b64 = str(data.get("signature_b64") or "")
        if not signature_b64:
            raise SigningError("signer_response_missing_signature")
        response_algorithm = data.get("algorithm")
        response_key_id = data.get("key_id")
        if response_algorithm is not None and str(response_algorithm) != self.algorithm:
            raise SigningError("signer_response_identity_mismatch")
        if response_key_id is not None and str(response_key_id) != self.key_id:
            raise SigningError("signer_response_identity_mismatch")
        return SignatureRecord(
            algorithm=self.algorithm,
            key_id=self.key_id,
            signature_b64=signature_b64,
            signer="external_http",
        )

    async def verify(self, digest: bytes, signature: SignatureRecord) -> bool:
        payload = {
            "operation": "verify",
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "digest_b64": base64.b64encode(digest).decode("ascii"),
            "signature_b64": signature.signature_b64,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.url, headers=self._headers(), json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise SigningError(f"signer_verify_failed:{type(exc).__name__}") from None
        response_algorithm = data.get("algorithm")
        response_key_id = data.get("key_id")
        if response_algorithm is not None and str(response_algorithm) != self.algorithm:
            raise SigningError("signer_response_identity_mismatch")
        if response_key_id is not None and str(response_key_id) != self.key_id:
            raise SigningError("signer_response_identity_mismatch")
        return bool(data.get("verified") is True)


class DualSigner:
    @classmethod
    def from_env(cls) -> "DualSigner":
        ed = ExternalHttpSigner(
            algorithm="Ed25519",
            url=os.getenv("SARA_ED25519_SIGNER_URL", "").strip(),
            key_id=os.getenv("SARA_ED25519_KEY_ID", "").strip(),
            token=os.getenv("SARA_ED25519_SIGNER_TOKEN", "").strip(),
        )
        ml = ExternalHttpSigner(
            algorithm="ML-DSA",
            url=os.getenv("SARA_ML_DSA_SIGNER_URL", "").strip(),
            key_id=os.getenv("SARA_ML_DSA_KEY_ID", "").strip(),
            token=os.getenv("SARA_ML_DSA_SIGNER_TOKEN", "").strip(),
        )
        return cls(ed, ml)

    def __init__(self, ed25519: Signer | None, ml_dsa: Signer | None):
        if ed25519 is None or ml_dsa is None:
            raise SigningError("dual_signer_requires_ed25519_and_ml_dsa")
        if ed25519.algorithm.lower() != "ed25519":
            raise SigningError("ed25519_signer_algorithm_mismatch")
        if ml_dsa.algorithm.lower().replace("_", "-") != "ml-dsa":
            raise SigningError("ml_dsa_signer_algorithm_mismatch")
        self.ed25519 = ed25519
        self.ml_dsa = ml_dsa

    async def sign_and_verify(self, digest: bytes) -> tuple[SignatureRecord, SignatureRecord]:
        if not isinstance(digest, (bytes, bytearray)) or not digest:
            raise SigningError("digest_required")
        digest_bytes = bytes(digest)
        try:
            ed_record = await self.ed25519.sign(digest_bytes)
            ml_record = await self.ml_dsa.sign(digest_bytes)
            if ed_record.algorithm.lower() != "ed25519":
                raise SigningError("ed25519_signature_record_algorithm_mismatch")
            if ml_record.algorithm.lower().replace("_", "-") != "ml-dsa":
                raise SigningError("ml_dsa_signature_record_algorithm_mismatch")
            ed_ok = await self.ed25519.verify(digest_bytes, ed_record)
            ml_ok = await self.ml_dsa.verify(digest_bytes, ml_record)
        except SigningError:
            raise
        except Exception as exc:
            raise SigningError(f"signing_failed:{type(exc).__name__}") from None
        if not ed_ok or not ml_ok:
            raise SigningError("signature_verification_failed")
        ed_record.verified = True
        ml_record.verified = True
        return ed_record, ml_record
