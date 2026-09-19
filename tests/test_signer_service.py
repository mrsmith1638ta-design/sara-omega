import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa
from fastapi.testclient import TestClient

from signer_service.main import KmsSignerEngine, SignerEngine, create_app


def _seed_client():
    engine = SignerEngine(
        bearer_token="unit-signer-token",
        ed25519_key_id="omega-ed25519-v1",
        ed25519_seed=b"E" * 32,
        ml_dsa_key_id="omega-ml-dsa-v1",
        ml_dsa_seed=b"M" * 32,
    )
    return TestClient(create_app(engine))


def _headers():
    return {"Authorization": "Bearer unit-signer-token"}


class FakeKms:
    def __init__(self):
        self.ed = ed25519.Ed25519PrivateKey.generate()
        self.ml = mldsa.MLDSA65PrivateKey.generate()
        self.calls = []

    def _private(self, key_id):
        if key_id == "arn:aws:kms:us-east-1:123:key/ed":
            return self.ed
        if key_id == "arn:aws:kms:us-east-1:123:key/ml":
            return self.ml
        raise RuntimeError("unknown key")

    def sign(self, **kwargs):
        self.calls.append(("sign", kwargs))
        return {"Signature": self._private(kwargs["KeyId"]).sign(kwargs["Message"])}

    def verify(self, **kwargs):
        self.calls.append(("verify", kwargs))
        try:
            self._private(kwargs["KeyId"]).public_key().verify(
                kwargs["Signature"],
                kwargs["Message"],
            )
            return {"SignatureValid": True}
        except InvalidSignature:
            return {"SignatureValid": False}

    def get_public_key(self, **kwargs):
        self.calls.append(("get_public_key", kwargs))
        key_id = kwargs["KeyId"]
        public = self._private(key_id).public_key()
        der = public.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        if key_id.endswith("/ed"):
            return {
                "PublicKey": der,
                "KeySpec": "ECC_NIST_EDWARDS25519",
                "KeyUsage": "SIGN_VERIFY",
                "SigningAlgorithms": ["ED25519_SHA_512"],
            }
        return {
            "PublicKey": der,
            "KeySpec": "ML_DSA_65",
            "KeyUsage": "SIGN_VERIFY",
            "SigningAlgorithms": ["ML_DSA_SHAKE_256"],
        }


def _kms_client():
    fake = FakeKms()
    engine = KmsSignerEngine(
        bearer_token="unit-signer-token",
        ed25519_key_id="arn:aws:kms:us-east-1:123:key/ed",
        ml_dsa_key_id="arn:aws:kms:us-east-1:123:key/ml",
        kms_client=fake,
    )
    return TestClient(create_app(engine)), fake


def test_health_is_public_and_does_not_expose_key_material():
    response = _seed_client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["backend"] == "seed-dev"
    assert body["algorithms"] == ["Ed25519", "ML-DSA"]
    assert body["key_ids"] == ["omega-ed25519-v1", "omega-ml-dsa-v1"]
    assert "seed" not in response.text.lower().replace("seed-dev", "")
    assert "private" not in response.text.lower().replace("private_key_exportable", "")


def test_software_signer_round_trip_remains_development_only():
    client = _seed_client()
    digest = b"D" * 64
    digest_b64 = base64.b64encode(digest).decode("ascii")

    for algorithm, key_id in (
        ("Ed25519", "omega-ed25519-v1"),
        ("ML-DSA", "omega-ml-dsa-v1"),
    ):
        signed = client.post(
            "/signer",
            headers=_headers(),
            json={
                "operation": "sign",
                "algorithm": algorithm,
                "key_id": key_id,
                "digest_b64": digest_b64,
            },
        )
        assert signed.status_code == 200
        signature_b64 = signed.json()["signature_b64"]
        assert signed.json()["backend"] == "seed-dev"

        verified = client.post(
            "/signer",
            headers=_headers(),
            json={
                "operation": "verify",
                "algorithm": algorithm,
                "key_id": key_id,
                "digest_b64": digest_b64,
                "signature_b64": signature_b64,
            },
        )
        assert verified.status_code == 200
        assert verified.json()["verified"] is True


def test_kms_signer_uses_raw_asymmetric_signing_and_never_loads_private_keys():
    client, fake = _kms_client()
    digest = b"K" * 64
    digest_b64 = base64.b64encode(digest).decode("ascii")

    cases = (
        (
            "Ed25519",
            "arn:aws:kms:us-east-1:123:key/ed",
            "ED25519_SHA_512",
        ),
        (
            "ML-DSA",
            "arn:aws:kms:us-east-1:123:key/ml",
            "ML_DSA_SHAKE_256",
        ),
    )
    for algorithm, key_id, signing_algorithm in cases:
        signed = client.post(
            "/signer",
            headers=_headers(),
            json={
                "operation": "sign",
                "algorithm": algorithm,
                "key_id": key_id,
                "digest_b64": digest_b64,
            },
        )
        assert signed.status_code == 200
        assert signed.json()["backend"] == "aws-kms"

        call = [call for call in fake.calls if call[0] == "sign"][-1][1]
        assert call["KeyId"] == key_id
        assert call["Message"] == digest
        assert call["MessageType"] == "RAW"
        assert call["SigningAlgorithm"] == signing_algorithm

        verified = client.post(
            "/signer",
            headers=_headers(),
            json={
                "operation": "verify",
                "algorithm": algorithm,
                "key_id": key_id,
                "digest_b64": digest_b64,
                "signature_b64": signed.json()["signature_b64"],
            },
        )
        assert verified.status_code == 200
        assert verified.json()["verified"] is True


def test_public_key_endpoint_exports_only_verification_material():
    client, _ = _kms_client()
    response = client.get("/public-keys")

    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "aws-kms"
    assert body["verification_only"] is True
    assert len(body["keys"]) == 2
    assert {item["algorithm"] for item in body["keys"]} == {"Ed25519", "ML-DSA"}
    assert all("BEGIN PUBLIC KEY" in item["public_key_pem"] for item in body["keys"])
    assert all(len(item["public_key_sha256"]) == 64 for item in body["keys"])
    assert "PRIVATE KEY" not in response.text
    assert "seed" not in response.text.lower()


def test_kms_signer_rejects_key_metadata_mismatch():
    client, fake = _kms_client()
    original = fake.get_public_key

    def wrong_usage(**kwargs):
        response = original(**kwargs)
        response["KeyUsage"] = "ENCRYPT_DECRYPT"
        return response

    fake.get_public_key = wrong_usage
    response = client.get("/public-keys")
    assert response.status_code == 503
    assert response.json()["detail"] == "kms_key_usage_mismatch"


def test_signer_rejects_missing_or_wrong_bearer_token():
    client, _ = _kms_client()
    payload = {
        "operation": "sign",
        "algorithm": "Ed25519",
        "key_id": "arn:aws:kms:us-east-1:123:key/ed",
        "digest_b64": base64.b64encode(b"D" * 64).decode("ascii"),
    }
    assert client.post("/signer", json=payload).status_code == 401
    assert client.post(
        "/signer",
        headers={"Authorization": "Bearer wrong"},
        json=payload,
    ).status_code == 401


def test_signer_rejects_wrong_key_id_or_digest_length():
    client, _ = _kms_client()
    wrong_key = client.post(
        "/signer",
        headers=_headers(),
        json={
            "operation": "sign",
            "algorithm": "Ed25519",
            "key_id": "other",
            "digest_b64": base64.b64encode(b"D" * 64).decode("ascii"),
        },
    )
    assert wrong_key.status_code == 400

    wrong_digest = client.post(
        "/signer",
        headers=_headers(),
        json={
            "operation": "sign",
            "algorithm": "ML-DSA",
            "key_id": "arn:aws:kms:us-east-1:123:key/ml",
            "digest_b64": base64.b64encode(b"short").decode("ascii"),
        },
    )
    assert wrong_digest.status_code == 400
