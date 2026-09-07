import base64

from fastapi.testclient import TestClient

from signer_service.main import SignerEngine, create_app


def _client():
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


def test_health_is_public_and_does_not_expose_key_material():
    response = _client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "ok": True,
        "algorithms": ["Ed25519", "ML-DSA"],
        "key_ids": ["omega-ed25519-v1", "omega-ml-dsa-v1"],
    }
    assert "seed" not in response.text.lower()
    assert "private" not in response.text.lower()


def test_sign_and_verify_round_trip_for_both_algorithms():
    client = _client()
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
        assert signed.json()["algorithm"] == algorithm
        assert signed.json()["key_id"] == key_id

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
        assert verified.json() == {
            "algorithm": algorithm,
            "key_id": key_id,
            "verified": True,
        }


def test_signer_rejects_missing_or_wrong_bearer_token():
    client = _client()
    payload = {
        "operation": "sign",
        "algorithm": "Ed25519",
        "key_id": "omega-ed25519-v1",
        "digest_b64": base64.b64encode(b"D" * 64).decode("ascii"),
    }
    assert client.post("/signer", json=payload).status_code == 401
    assert client.post(
        "/signer",
        headers={"Authorization": "Bearer wrong"},
        json=payload,
    ).status_code == 401


def test_signer_rejects_wrong_key_id_or_digest_length():
    client = _client()
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
            "key_id": "omega-ml-dsa-v1",
            "digest_b64": base64.b64encode(b"short").decode("ascii"),
        },
    )
    assert wrong_digest.status_code == 400
