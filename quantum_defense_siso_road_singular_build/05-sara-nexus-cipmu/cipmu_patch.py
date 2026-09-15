import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from flask import jsonify, request


PATCH_VERSION = "SARA-QUANTUM-DEFENSE-ALT-001-IMPL-v1.3"
AUTH_MAX_SKEW_SECONDS = int(os.environ.get("SARA_OPERATION_AUTH_MAX_SKEW_SECONDS", "300"))
SEAL_STORE_PATH = Path(os.environ.get("SARA_CIPMU_SEAL_STORE", "/var/lib/sara-cipmu/seal-store.json"))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _metadata(path: str) -> str:
    url = "http://metadata.google.internal/computeMetadata/v1/" + path.lstrip("/")
    req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return ""


def _identity_token(audience: str) -> str:
    return _metadata(
        "instance/service-accounts/default/identity?audience="
        + urllib.parse.quote(audience.rstrip("/"), safe="")
    )


def _hash(data) -> str:
    payload = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha3_512(payload).hexdigest()


def _load_seal_store() -> dict:
    if not SEAL_STORE_PATH.exists():
        return {}
    return json.loads(SEAL_STORE_PATH.read_text(encoding="utf-8") or "{}")


def _save_seal_store(store: dict) -> None:
    SEAL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SEAL_STORE_PATH.with_suffix(SEAL_STORE_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(store, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(SEAL_STORE_PATH)


def _require_operation_authorization(operation: str) -> tuple[dict | None, int | None]:
    secret = os.environ.get("SARA_OPERATION_HMAC_SECRET", "")
    caller = request.headers.get("X-SARA-Caller", "")
    timestamp = request.headers.get("X-SARA-Timestamp", "")
    supplied_operation = request.headers.get("X-SARA-Operation", "")
    signature = request.headers.get("X-SARA-Signature", "")
    if not secret:
        return {"error": "operation_authorization_secret_unconfigured"}, 503
    if caller != "sara-omega-control-plane" or supplied_operation != operation:
        return {"error": "operation_authorization_scope_denied"}, 403
    try:
        observed = int(timestamp)
    except ValueError:
        return {"error": "operation_authorization_timestamp_invalid"}, 401
    if abs(int(time.time()) - observed) > AUTH_MAX_SKEW_SECONDS:
        return {"error": "operation_authorization_timestamp_stale"}, 401
    body_hash = hashlib.sha3_512(request.get_data() or b"").hexdigest()
    canonical = f"{caller}|{operation}|{timestamp}|{body_hash}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha3_512).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return {"error": "operation_authorization_signature_mismatch"}, 401
    return None, None


def _require_verified_attestation() -> tuple[dict | None, int | None]:
    attestation = _attestation_payload()
    if not attestation["verified"]:
        return {
            "error": "attestation_currently_inaccessible",
            "evidence_state": "CURRENTLY_INACCESSIBLE",
            "attestation": attestation,
        }, 503
    return None, None


def _attestation_payload() -> dict:
    project = os.environ.get("SARA_ENCLAVE_PROJECT") or os.environ.get("GCP_PROJECT") or "sara-soverigne-modules"
    service = os.environ.get("K_SERVICE", "sara-nexus-cipmu")
    revision = os.environ.get("K_REVISION", "")
    token = _identity_token("https://" + service)
    verified_token = os.environ.get("SARA_CIPMU_VERIFIED_ATTESTATION_TOKEN", "")
    confidential_enabled = os.environ.get("SARA_CONFIDENTIAL_COMPUTING_ENABLED", "false").lower() == "true"
    verified = confidential_enabled and bool(verified_token) and hmac.compare_digest(
        hashlib.sha3_512(token.encode("utf-8")).hexdigest() if token else "",
        hashlib.sha3_512(verified_token.encode("utf-8")).hexdigest(),
    )
    return {
        "service": service,
        "revision": revision,
        "project": project,
        "confidential_computing_enabled": confidential_enabled,
        "metadata_identity_available": bool(token),
        "token_hash_sha3_512": hashlib.sha3_512(token.encode("utf-8")).hexdigest() if token else "",
        "verified": verified,
        "evidence_state": "VERIFIED" if verified else "CURRENTLY_INACCESSIBLE",
        "timestamp_epoch": int(time.time()),
    }


def register_cipmu(app):
    @app.get("/v1/cipmu/enclave-status")
    def enclave_status():
        attestation = _attestation_payload()
        store = _load_seal_store()
        return jsonify({
            "service": "sara-nexus-cipmu",
            "status": "operational" if attestation["verified"] else "blocked",
            "patch": PATCH_VERSION,
            "attestation": attestation,
            "sealed_records": len(store),
            "seal_store": str(SEAL_STORE_PATH),
            "ppsim_url": os.environ.get("SARA_PQC_PPSIM_URL", ""),
        })

    @app.post("/v1/cipmu/attest")
    def attest():
        error, status = _require_operation_authorization("cipmu.attest")
        if error:
            return jsonify(error), status
        return jsonify({
            "service": "sara-nexus-cipmu",
            "patch": PATCH_VERSION,
            "attestation": _attestation_payload(),
        })

    @app.post("/v1/cipmu/seal")
    def seal():
        error, status = _require_operation_authorization("cipmu.seal")
        if error:
            return jsonify(error), status
        error, status = _require_verified_attestation()
        if error:
            return jsonify(error), status
        body = request.get_json(silent=True) or {}
        payload = body.get("payload")
        context = body.get("context") or {}
        attestation = _attestation_payload()
        payload_hash = _hash(payload)
        record_id = "SEAL-" + hashlib.sha3_512((payload_hash + str(time.time())).encode("utf-8")).hexdigest()[:24].upper()
        key = os.environ.get("SARA_CIPMU_SEAL_HMAC_KEY", "")
        if not key:
            return jsonify({"sealed": False, "reason": "seal_hmac_key_unconfigured"}), 503
        mac = hmac.new(key.encode("utf-8"), (payload_hash + _hash(context) + attestation["token_hash_sha3_512"]).encode("utf-8"), hashlib.sha3_512).digest()
        store = _load_seal_store()
        store[record_id] = {
            "payload_hash_sha3_512": payload_hash,
            "context_hash_sha3_512": _hash(context),
            "attestation_hash_sha3_512": _hash(attestation),
            "seal_mac": _b64(mac),
            "timestamp_epoch": int(time.time()),
        }
        _save_seal_store(store)
        return jsonify({
            "sealed": True,
            "record_id": record_id,
            "payload_hash_sha3_512": payload_hash,
            "raw_payload_returned": False,
            "algorithm": "SHA3-512-bound enclave seal",
        })

    @app.post("/v1/cipmu/unseal")
    def unseal():
        error, status = _require_operation_authorization("cipmu.unseal")
        if error:
            return jsonify(error), status
        error, status = _require_verified_attestation()
        if error:
            return jsonify(error), status
        body = request.get_json(silent=True) or {}
        record_id = str(body.get("record_id") or "")
        record = _load_seal_store().get(record_id)
        if not record:
            return jsonify({"unsealed": False, "reason": "record_not_found"}), 404
        return jsonify({
            "unsealed": True,
            "record_id": record_id,
            "payload_hash_sha3_512": record["payload_hash_sha3_512"],
            "raw_payload_returned": False,
            "attestation_required": True,
        })

    return app
