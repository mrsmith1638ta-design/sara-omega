import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request

import oqs
from fastapi import HTTPException, Request

PATCH_VERSION = "SARA-QUANTUM-DEFENSE-ALT-001-IMPL-v1.3"
KEM_ALG = "ML-KEM-1024"
SIG_ALG = "ML-DSA-87"
PROJECT_ID = os.environ.get("PROJECT_ID", "sara-soverigne-modules")
KEM_SECRET_NAME = os.environ.get("SARA_PQC_KEM_SECRET_NAME", "sara-pqc-kyber-private-key-native-v13")
SIG_SECRET_NAME = os.environ.get("SARA_PQC_SIG_SECRET_NAME", "sara-pqc-dilithium-private-key-native-v13")
AUTH_MAX_SKEW_SECONDS = int(os.environ.get("SARA_OPERATION_AUTH_MAX_SKEW_SECONDS", "300"))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _bundle(raw: str, algorithm: str) -> dict:
    parsed = json.loads(raw)
    if parsed.get("algorithm") != algorithm:
        raise ValueError(f"expected algorithm {algorithm}")
    _unb64(parsed["secret_key"]); _unb64(parsed["public_key"])
    return parsed


def _access_token() -> str:
    req = urllib.request.Request("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)["access_token"]


def _secret_request(url: str, method: str = "GET", body: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers={"Authorization": "Bearer " + _access_token(), "Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def _secret_bundle(secret_name: str, algorithm: str, env_name: str) -> dict:
    try:
        result = _secret_request(f"https://secretmanager.googleapis.com/v1/projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest:access")
        return _bundle(base64.b64decode(result["payload"]["data"]).decode(), algorithm)
    except Exception:
        raw = os.environ.get(env_name, "")
        if not raw:
            raise
        return _bundle(raw, algorithm)


def _add_secret_version(secret_name: str, bundle: dict) -> str:
    encoded = base64.b64encode(json.dumps(bundle, separators=(",", ":")).encode()).decode()
    result = _secret_request(f"https://secretmanager.googleapis.com/v1/projects/{PROJECT_ID}/secrets/{secret_name}:addVersion", "POST", {"payload": {"data": encoded}})
    return result["name"].rsplit("/", 1)[-1]


def _kem_keys() -> dict:
    return _secret_bundle(KEM_SECRET_NAME, KEM_ALG, "SARA_PQC_KYBER_PRIVATE_KEY")


def _sig_keys() -> dict:
    return _secret_bundle(SIG_SECRET_NAME, SIG_ALG, "SARA_PQC_DILITHIUM_PRIVATE_KEY")


def _assert_algorithms() -> None:
    missing = []
    if KEM_ALG not in set(oqs.get_enabled_kem_mechanisms()): missing.append(KEM_ALG)
    if SIG_ALG not in set(oqs.get_enabled_sig_mechanisms()): missing.append(SIG_ALG)
    if missing: raise RuntimeError("required OQS mechanisms unavailable: " + ", ".join(missing))


_assert_algorithms()


def _status() -> dict:
    return {"service": "sara-nexus-ppsim", "status": "operational", "patch": PATCH_VERSION, "algorithms": {"kem": KEM_ALG, "signature": SIG_ALG, "design_aliases": {"kem": "CRYSTALS-Kyber-1024", "signature": "CRYSTALS-Dilithium-L5"}}, "mode": "liboqs_native", "liboqs_version": oqs.oqs_version(), "liboqs_python_version": oqs.oqs_python_version(), "private_keys_source": {"kem": KEM_SECRET_NAME, "signature": SIG_SECRET_NAME}, "generated_at": int(time.time())}


async def _json(request: Request) -> dict:
    try: return await request.json()
    except Exception: return {}


def _hash_secret(secret: bytes) -> str:
    return hashlib.sha3_512(secret).hexdigest()


async def _require_operation_authorization(request: Request, operation: str) -> None:
    secret = os.environ.get("SARA_OPERATION_HMAC_SECRET", "")
    caller = request.headers.get("X-SARA-Caller", "")
    timestamp = request.headers.get("X-SARA-Timestamp", "")
    supplied_operation = request.headers.get("X-SARA-Operation", "")
    signature = request.headers.get("X-SARA-Signature", "")
    if not secret:
        raise HTTPException(status_code=503, detail="operation_authorization_secret_unconfigured")
    if caller != "sara-omega-control-plane" or supplied_operation != operation:
        raise HTTPException(status_code=403, detail="operation_authorization_scope_denied")
    try:
        observed = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="operation_authorization_timestamp_invalid") from exc
    if abs(int(time.time()) - observed) > AUTH_MAX_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="operation_authorization_timestamp_stale")
    body = await request.body()
    body_hash = hashlib.sha3_512(body).hexdigest()
    canonical = f"{caller}|{operation}|{timestamp}|{body_hash}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha3_512).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="operation_authorization_signature_mismatch")


def register_pqc(app):
    @app.get("/v1/pqc/public-key")
    def public_key():
        kem_keys = _kem_keys(); sig_keys = _sig_keys()
        return {**_status(), "public_keys": {"kem": kem_keys["public_key"], "signature": sig_keys["public_key"]}}

    @app.post("/v1/pqc/generate-keypair")
    async def generate_keypair(request: Request):
        await _require_operation_authorization(request, "pqc.generate-keypair")
        with oqs.KeyEncapsulation(KEM_ALG) as kem, oqs.Signature(SIG_ALG) as sig:
            return {**_status(), "generated": True, "public_keys": {"kem": _b64(kem.generate_keypair()), "signature": _b64(sig.generate_keypair())}, "private_key_material": "not_returned", "persistent": False}

    @app.post("/v1/pqc/rotate-keys")
    async def rotate_keys(request: Request):
        await _require_operation_authorization(request, "pqc.rotate-keys")
        with oqs.KeyEncapsulation(KEM_ALG) as kem:
            kem_public = kem.generate_keypair(); kem_secret = kem.export_secret_key()
        with oqs.Signature(SIG_ALG) as sig:
            sig_public = sig.generate_keypair(); sig_secret = sig.export_secret_key()
        kem_bundle = {"algorithm": KEM_ALG, "public_key": _b64(kem_public), "secret_key": _b64(kem_secret)}
        sig_bundle = {"algorithm": SIG_ALG, "public_key": _b64(sig_public), "secret_key": _b64(sig_secret)}
        return {**_status(), "rotated": True, "secret_versions": {"kem": _add_secret_version(KEM_SECRET_NAME, kem_bundle), "signature": _add_secret_version(SIG_SECRET_NAME, sig_bundle)}, "public_keys": {"kem": kem_bundle["public_key"], "signature": sig_bundle["public_key"]}, "private_key_material": "not_returned"}

    @app.post("/v1/pqc/encapsulate")
    async def encapsulate(request: Request):
        await _require_operation_authorization(request, "pqc.encapsulate")
        body = await _json(request); keys = _kem_keys(); public_key = _unb64(str(body.get("public_key") or keys["public_key"]))
        with oqs.KeyEncapsulation(KEM_ALG) as kem: ciphertext, shared_secret = kem.encap_secret(public_key)
        return {"algorithm": KEM_ALG, "ciphertext": _b64(ciphertext), "shared_secret_hash_sha3_512": _hash_secret(shared_secret), "secret_material_returned": False, "mode": "liboqs_native"}

    @app.post("/v1/pqc/decapsulate")
    async def decapsulate(request: Request):
        await _require_operation_authorization(request, "pqc.decapsulate")
        body = await _json(request); keys = _kem_keys(); ciphertext = _unb64(str(body.get("ciphertext") or ""))
        with oqs.KeyEncapsulation(KEM_ALG, _unb64(keys["secret_key"])) as kem: shared_secret = kem.decap_secret(ciphertext)
        return {"algorithm": KEM_ALG, "shared_secret_hash_sha3_512": _hash_secret(shared_secret), "secret_material_returned": False, "mode": "liboqs_native"}

    @app.post("/v1/pqc/sign")
    async def sign(request: Request):
        await _require_operation_authorization(request, "pqc.sign")
        body = await _json(request); keys = _sig_keys(); message = str(body.get("message") or body.get("payload") or "").encode()
        with oqs.Signature(SIG_ALG, _unb64(keys["secret_key"])) as signer: signature = signer.sign(message)
        return {"algorithm": SIG_ALG, "signature": _b64(signature), "public_key": keys["public_key"], "mode": "liboqs_native"}

    @app.post("/v1/pqc/verify")
    async def verify(request: Request):
        body = await _json(request); keys = _sig_keys(); message = str(body.get("message") or body.get("payload") or "").encode(); signature = _unb64(str(body.get("signature") or "")); public_key = _unb64(str(body.get("public_key") or keys["public_key"]))
        with oqs.Signature(SIG_ALG) as verifier: valid = verifier.verify(message, signature, public_key)
        return {"algorithm": SIG_ALG, "valid": bool(valid), "mode": "liboqs_native"}

    return app
