from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import textwrap
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


Algorithm = Literal["Ed25519", "ML-DSA"]


class SignerRequest(BaseModel):
    operation: Literal["sign", "verify"]
    algorithm: Algorithm
    key_id: str
    digest_b64: str
    signature_b64: str | None = None


@dataclass(frozen=True)
class PublicKeyRecord:
    algorithm: Algorithm
    key_id: str
    key_spec: str
    signing_algorithm: str
    public_key_pem: str
    public_key_sha256: str

    def public_dict(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "key_spec": self.key_spec,
            "signing_algorithm": self.signing_algorithm,
            "public_key_pem": self.public_key_pem,
            "public_key_sha256": self.public_key_sha256,
        }


class SignerBackend(Protocol):
    backend_name: str
    ed25519_key_id: str
    ml_dsa_key_id: str

    def authorize(self, authorization: str | None) -> None: ...
    def sign(self, algorithm: str, key_id: str, digest: bytes) -> bytes: ...
    def verify(self, algorithm: str, key_id: str, digest: bytes, signature: bytes) -> bool: ...
    def public_keys(self) -> list[PublicKeyRecord]: ...


class _Common:
    backend_name = "unknown"

    def __init__(self, *, bearer_token: str, ed25519_key_id: str, ml_dsa_key_id: str) -> None:
        if not bearer_token:
            raise ValueError("bearer_token_required")
        if not ed25519_key_id or not ml_dsa_key_id:
            raise ValueError("key_id_required")
        self._bearer_token = bearer_token
        self.ed25519_key_id = ed25519_key_id
        self.ml_dsa_key_id = ml_dsa_key_id

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


class SignerEngine(_Common):
    """Development-only software signer.

    Production loading never selects this backend unless the operator explicitly
    sets OMEGA_SIGNER_BACKEND=seed-dev and OMEGA_ALLOW_INSECURE_SEED_SIGNER=true.
    """

    backend_name = "seed-dev"

    def __init__(
        self,
        *,
        bearer_token: str,
        ed25519_key_id: str,
        ed25519_seed: bytes,
        ml_dsa_key_id: str,
        ml_dsa_seed: bytes,
    ) -> None:
        super().__init__(
            bearer_token=bearer_token,
            ed25519_key_id=ed25519_key_id,
            ml_dsa_key_id=ml_dsa_key_id,
        )
        if len(ed25519_seed) != 32 or len(ml_dsa_seed) != 32:
            raise ValueError("signer_seed_must_be_32_bytes")
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

    @staticmethod
    def _pem_from_public_key(public_key: Any) -> str:
        from cryptography.hazmat.primitives import serialization

        return public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def public_keys(self) -> list[PublicKeyRecord]:
        records = []
        for algorithm, key_id, public_key, key_spec, signing_algorithm in (
            (
                "Ed25519",
                self.ed25519_key_id,
                self._ed25519_private.public_key(),
                "ECC_NIST_EDWARDS25519",
                "ED25519_SHA_512",
            ),
            (
                "ML-DSA",
                self.ml_dsa_key_id,
                self._ml_dsa_private.public_key(),
                "ML_DSA_65",
                "ML_DSA_SHAKE_256",
            ),
        ):
            pem = self._pem_from_public_key(public_key)
            der = base64.b64decode("".join(
                line for line in pem.splitlines() if not line.startswith("-----")
            ))
            records.append(
                PublicKeyRecord(
                    algorithm=algorithm,
                    key_id=key_id,
                    key_spec=key_spec,
                    signing_algorithm=signing_algorithm,
                    public_key_pem=pem,
                    public_key_sha256=hashlib.sha256(der).hexdigest(),
                )
            )
        return records


class KmsSignerEngine(_Common):
    """AWS KMS/HSM-backed asymmetric signer.

    Only opaque KMS key identifiers are held by the service. Private key
    material is never loaded into process memory.
    """

    backend_name = "aws-kms"
    _AWS = {
        "Ed25519": {
            "key_spec": "ECC_NIST_EDWARDS25519",
            "signing_algorithm": "ED25519_SHA_512",
        },
        "ML-DSA": {
            "key_spec": "ML_DSA_65",
            "signing_algorithm": "ML_DSA_SHAKE_256",
        },
    }

    def __init__(
        self,
        *,
        bearer_token: str,
        ed25519_key_id: str,
        ml_dsa_key_id: str,
        kms_client: Any,
    ) -> None:
        super().__init__(
            bearer_token=bearer_token,
            ed25519_key_id=ed25519_key_id,
            ml_dsa_key_id=ml_dsa_key_id,
        )
        if kms_client is None:
            raise ValueError("kms_client_required")
        self._kms = kms_client
        self._public_key_cache: dict[str, PublicKeyRecord] = {}

    @classmethod
    def from_env(cls) -> "KmsSignerEngine":
        try:
            import boto3
        except ImportError as exc:
            raise ValueError("boto3_required_for_aws_kms_backend") from exc

        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "")).strip()
        client = boto3.client("kms", region_name=region or None)
        return cls(
            bearer_token=os.getenv("OMEGA_SIGNER_TOKEN", "").strip(),
            ed25519_key_id=os.getenv("OMEGA_ED25519_KMS_KEY_ID", "").strip(),
            ml_dsa_key_id=os.getenv("OMEGA_ML_DSA_KMS_KEY_ID", "").strip(),
            kms_client=client,
        )

    def _settings(self, algorithm: str) -> dict[str, str]:
        try:
            return self._AWS[algorithm]
        except KeyError:
            raise HTTPException(status_code=400, detail="unsupported_algorithm") from None

    def sign(self, algorithm: str, key_id: str, digest: bytes) -> bytes:
        self._validate_key_id(algorithm, key_id)
        settings = self._settings(algorithm)
        try:
            response = self._kms.sign(
                KeyId=key_id,
                Message=digest,
                MessageType="RAW",
                SigningAlgorithm=settings["signing_algorithm"],
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="kms_sign_unavailable") from exc
        signature = response.get("Signature")
        if not isinstance(signature, (bytes, bytearray)) or not signature:
            raise HTTPException(status_code=503, detail="kms_signature_missing")
        return bytes(signature)

    def verify(self, algorithm: str, key_id: str, digest: bytes, signature: bytes) -> bool:
        self._validate_key_id(algorithm, key_id)
        settings = self._settings(algorithm)
        try:
            response = self._kms.verify(
                KeyId=key_id,
                Message=digest,
                MessageType="RAW",
                Signature=signature,
                SigningAlgorithm=settings["signing_algorithm"],
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="kms_verify_unavailable") from exc
        return bool(response.get("SignatureValid"))

    @staticmethod
    def _pem_from_der(der: bytes) -> str:
        encoded = base64.b64encode(der).decode("ascii")
        body = "\n".join(textwrap.wrap(encoded, 64))
        return f"-----BEGIN PUBLIC KEY-----\n{body}\n-----END PUBLIC KEY-----\n"

    def _public_key(self, algorithm: str, key_id: str) -> PublicKeyRecord:
        self._validate_key_id(algorithm, key_id)
        if key_id in self._public_key_cache:
            return self._public_key_cache[key_id]

        expected = self._settings(algorithm)
        try:
            response = self._kms.get_public_key(KeyId=key_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="kms_public_key_unavailable") from exc

        public_key = response.get("PublicKey")
        if not isinstance(public_key, (bytes, bytearray)) or not public_key:
            raise HTTPException(status_code=503, detail="kms_public_key_missing")
        if response.get("KeyUsage") != "SIGN_VERIFY":
            raise HTTPException(status_code=503, detail="kms_key_usage_mismatch")
        if response.get("KeySpec") != expected["key_spec"]:
            raise HTTPException(status_code=503, detail="kms_key_spec_mismatch")
        algorithms = set(response.get("SigningAlgorithms") or ())
        if expected["signing_algorithm"] not in algorithms:
            raise HTTPException(status_code=503, detail="kms_signing_algorithm_mismatch")

        der = bytes(public_key)
        record = PublicKeyRecord(
            algorithm=algorithm,
            key_id=key_id,
            key_spec=expected["key_spec"],
            signing_algorithm=expected["signing_algorithm"],
            public_key_pem=self._pem_from_der(der),
            public_key_sha256=hashlib.sha256(der).hexdigest(),
        )
        self._public_key_cache[key_id] = record
        return record

    def public_keys(self) -> list[PublicKeyRecord]:
        return [
            self._public_key("Ed25519", self.ed25519_key_id),
            self._public_key("ML-DSA", self.ml_dsa_key_id),
        ]


def signer_from_env() -> SignerBackend:
    backend = os.getenv("OMEGA_SIGNER_BACKEND", "aws-kms").strip().lower()
    if backend == "aws-kms":
        return KmsSignerEngine.from_env()
    if backend == "seed-dev":
        if os.getenv("OMEGA_ALLOW_INSECURE_SEED_SIGNER", "false").lower() != "true":
            raise ValueError("seed_signer_disabled")
        return SignerEngine.from_env()
    raise ValueError("unsupported_signer_backend")


def create_app(engine: SignerBackend | None = None) -> FastAPI:
    app = FastAPI(title="SARA OMEGA KMS Signer", version="2.0.0")
    app.state.engine = engine

    def current_engine() -> SignerBackend:
        if app.state.engine is None:
            app.state.engine = signer_from_env()
        return app.state.engine

    @app.get("/health")
    def health() -> dict[str, object]:
        active = current_engine()
        return {
            "ok": True,
            "backend": active.backend_name,
            "private_key_exportable": False if active.backend_name == "aws-kms" else True,
            "algorithms": ["Ed25519", "ML-DSA"],
            "key_ids": [active.ed25519_key_id, active.ml_dsa_key_id],
        }

    @app.get("/public-keys")
    def public_keys() -> dict[str, object]:
        active = current_engine()
        return {
            "backend": active.backend_name,
            "verification_only": True,
            "keys": [record.public_dict() for record in active.public_keys()],
        }

    @app.post("/signer")
    def signer(request: SignerRequest, authorization: str | None = Header(default=None)) -> dict[str, object]:
        active = current_engine()
        active.authorize(authorization)
        digest = _Common.decode_digest(request.digest_b64)
        if request.operation == "sign":
            signature = active.sign(request.algorithm, request.key_id, digest)
            return {
                "algorithm": request.algorithm,
                "key_id": request.key_id,
                "signature_b64": base64.b64encode(signature).decode("ascii"),
                "backend": active.backend_name,
            }

        signature = _Common.decode_signature(request.signature_b64)
        verified = active.verify(request.algorithm, request.key_id, digest, signature)
        return {
            "algorithm": request.algorithm,
            "key_id": request.key_id,
            "verified": verified,
            "backend": active.backend_name,
        }

    return app


app = create_app()
