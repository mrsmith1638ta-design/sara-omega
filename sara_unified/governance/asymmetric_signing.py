"""Asymmetric signing client for SARA governance evidence.

Production signing is delegated to the isolated signer service. That service is
expected to be backed by AWS KMS asymmetric keys. This client never receives or
stores private key material.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class EvidenceSignature:
    algorithm: str
    key_id: str
    signature_b64: str
    backend: str


class EvidenceSigner(Protocol):
    def sign_digest(self, digest: bytes) -> tuple[EvidenceSignature, ...]: ...


class DualKmsSignerClient:
    """Request Ed25519 and ML-DSA signatures from the SARA signing authority."""

    def __init__(
        self,
        *,
        base_url: str,
        bearer_token: str,
        ed25519_key_id: str,
        ml_dsa_key_id: str,
        timeout_seconds: float = 5.0,
        require_kms_backend: bool = True,
        client: Any | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("signer_base_url_required")
        if not bearer_token.strip():
            raise ValueError("signer_bearer_token_required")
        if not ed25519_key_id.strip() or not ml_dsa_key_id.strip():
            raise ValueError("signer_key_ids_required")
        if timeout_seconds <= 0:
            raise ValueError("signer_timeout_must_be_positive")

        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.ed25519_key_id = ed25519_key_id
        self.ml_dsa_key_id = ml_dsa_key_id
        self.timeout_seconds = timeout_seconds
        self.require_kms_backend = require_kms_backend
        self._client = client


    def ready(self) -> bool:
        try:
            if self._client is not None:
                response = self._client.get(f"{self.base_url}/health")
            else:
                response = httpx.get(
                    f"{self.base_url}/health",
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                )
            if response.status_code != 200:
                return False
            body = response.json()
        except Exception:
            return False
        if not isinstance(body, dict) or body.get("ok") is not True:
            return False
        if self.require_kms_backend and body.get("backend") != "aws-kms":
            return False
        if self.require_kms_backend and body.get("private_key_exportable") is not False:
            return False
        key_ids = body.get("key_ids")
        return key_ids == [self.ed25519_key_id, self.ml_dsa_key_id]

    def _post(self, payload: dict[str, str]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        if self._client is not None:
            response = self._client.post(
                f"{self.base_url}/signer",
                headers=headers,
                json=payload,
            )
        else:
            try:
                response = httpx.post(
                    f"{self.base_url}/signer",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                )
            except httpx.HTTPError as exc:
                raise RuntimeError("kms_signer_unreachable") from exc

        if response.status_code != 200:
            raise RuntimeError(f"kms_signer_rejected:{response.status_code}")
        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError("kms_signer_invalid_response") from exc
        if not isinstance(body, dict):
            raise RuntimeError("kms_signer_invalid_response")
        return body

    def _sign_one(self, algorithm: str, key_id: str, digest_b64: str) -> EvidenceSignature:
        body = self._post(
            {
                "operation": "sign",
                "algorithm": algorithm,
                "key_id": key_id,
                "digest_b64": digest_b64,
            }
        )
        if body.get("algorithm") != algorithm or body.get("key_id") != key_id:
            raise RuntimeError("kms_signer_identity_mismatch")
        backend = str(body.get("backend", ""))
        if self.require_kms_backend and backend != "aws-kms":
            raise RuntimeError("kms_signer_backend_not_hardware_backed")
        signature_b64 = body.get("signature_b64")
        if not isinstance(signature_b64, str) or not signature_b64:
            raise RuntimeError("kms_signer_signature_missing")
        try:
            decoded = base64.b64decode(signature_b64, validate=True)
        except Exception as exc:
            raise RuntimeError("kms_signer_signature_invalid_base64") from exc
        if not decoded:
            raise RuntimeError("kms_signer_signature_empty")
        return EvidenceSignature(
            algorithm=algorithm,
            key_id=key_id,
            signature_b64=signature_b64,
            backend=backend,
        )

    def sign_digest(self, digest: bytes) -> tuple[EvidenceSignature, ...]:
        if len(digest) != 64:
            raise ValueError("governance_signing_digest_must_be_64_bytes")
        digest_b64 = base64.b64encode(digest).decode("ascii")
        # Both signatures are required. A partial signature set is never returned.
        ed = self._sign_one("Ed25519", self.ed25519_key_id, digest_b64)
        ml = self._sign_one("ML-DSA", self.ml_dsa_key_id, digest_b64)
        return (ed, ml)
