import base64
import hashlib
import json
import os
import secrets
import time
import urllib.request

from google.cloud import kms

PROJECT = os.environ.get("PROJECT_ID", "sara-soverigne-modules")
LOCATION = os.environ.get("KMS_LOCATION", "us-central1")
KEYRING = os.environ.get("KMS_KEYRING", "sara-cipmu-confidential")
KEY = os.environ.get("KMS_KEY", "cipmu-seal-key")
AUDIENCE = os.environ.get("ATTESTATION_AUDIENCE", "sara-cipmu-step6e")


def sha3(value: bytes) -> str:
    return hashlib.sha3_512(value).hexdigest()


def get_attestation_token(nonce: str) -> str:
    candidates = [
        "/run/container_launcher/attestation_verifier_claims_token",
        "/run/container_launcher/attestation_token",
        "/run/secrets/tokens/attestation-token",
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                token = handle.read().strip()
            if token:
                return token
        except FileNotFoundError:
            continue
    try:
        available = sorted(os.listdir("/run/container_launcher"))
    except Exception:
        available = []
    raise RuntimeError("verified attestation token file not found; launcher files=" + ",".join(available))

def jwt_claims(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise RuntimeError("attestation response is not a JWT")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def kms_roundtrip(plaintext: bytes) -> dict:
    client = kms.KeyManagementServiceClient()
    name = client.crypto_key_path(PROJECT, LOCATION, KEYRING, KEY)
    encrypted = client.encrypt(request={"name": name, "plaintext": plaintext})
    decrypted = client.decrypt(request={"name": name, "ciphertext": encrypted.ciphertext})
    return {
        "plaintext_hash_sha3_512": sha3(plaintext),
        "ciphertext_hash_sha3_512": sha3(encrypted.ciphertext),
        "roundtrip_valid": decrypted.plaintext == plaintext,
        "raw_plaintext_returned": False,
    }


def main():
    nonce = secrets.token_hex(32)
    token = get_attestation_token(nonce)
    claims = jwt_claims(token)
    seal = kms_roundtrip(b"SARA-CIPMU-STEP6E-TEST:" + secrets.token_bytes(32))
    evidence = {
        "event": "CIPMU_EVIDENCE",
        "status": "PASS" if seal["roundtrip_valid"] else "FAIL",
        "attestation": {
            "jwt_present": True,
            "issuer": claims.get("iss"),
            "audience": claims.get("aud"),
            "submods": claims.get("submods", {}),
            "token_hash_sha3_512": sha3(token.encode()),
            "token_returned": False,
        },
        "kms_seal": seal,
        "timestamp_epoch": int(time.time()),
    }
    print(json.dumps(evidence, sort_keys=True), flush=True)
    if evidence["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

