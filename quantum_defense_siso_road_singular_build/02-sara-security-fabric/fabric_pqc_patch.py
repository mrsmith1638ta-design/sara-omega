import json
import os
import hmac
import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

from flask import jsonify, request

PATCH_VERSION = "SARA-QUANTUM-DEFENSE-ALT-001-IMPL-v1.3"
PROJECT_ID = os.environ.get("PROJECT_ID", "sara-soverigne-modules")
ROTATION_COLLECTION = os.environ.get("SARA_PQC_ROTATION_COLLECTION", "sara_pqc_rotation_events")


def _identity_token(audience: str) -> str:
    url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=" + urllib.parse.quote(audience.rstrip("/"), safe="")
    req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode()


def _call_json(base_url: str, path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, data=json.dumps(body or {}).encode() if method == "POST" else None, headers={"Authorization": "Bearer " + _identity_token(os.environ.get("SARA_PQC_PPSIM_AUDIENCE", base_url)), "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": "http_error", "detail": exc.read().decode(errors="replace")[:1000]}
    except Exception as exc:
        return 503, {"error": "call_failed", "detail": str(exc)}


def _audit_rotation(event: dict) -> str:
    from google.cloud import firestore
    event_id = "pqc-rotation-" + uuid.uuid4().hex
    firestore.Client(project=PROJECT_ID).collection(ROTATION_COLLECTION).document(event_id).set(event)
    return event_id


def _ppsim_status() -> tuple[int, dict]:
    url = os.environ.get("SARA_PQC_PPSIM_URL", "")
    if not url:
        return 500, {"error": "missing_SARA_PQC_PPSIM_URL"}
    return _call_json(url, "/v1/pqc/public-key")


def register_fabric_pqc(app):
    @app.post("/v1/access/check")
    def qnf_access_check():
        raw = request.get_data(cache=True, as_text=True)
        timestamp = request.headers.get("X-SARA-Timestamp", "")
        signature = request.headers.get("X-SARA-Signature", "")
        caller = request.headers.get("X-SARA-Module", "")
        secret = os.environ.get("SARA_QNF_SECURITY_HMAC_SECRET", "")
        if not secret or not timestamp or not signature or caller != "sara-quantum-nexus-fusion":
            return jsonify({"allowed": False, "reason": "authentication_failed"}), 401
        try:
            if abs(int(time.time()) - int(timestamp)) > 120:
                return jsonify({"allowed": False, "reason": "timestamp_outside_window"}), 401
        except ValueError:
            return jsonify({"allowed": False, "reason": "invalid_timestamp"}), 401
        canonical = f"POST\n/v1/access/check\n{timestamp}\n{raw}".encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return jsonify({"allowed": False, "reason": "signature_mismatch"}), 401
        body = request.get_json(silent=True) or {}
        allowed_requesters = {
            "sara-quantum-problem-solving-ecosystem",
            "sara-quantum-accelerator",
        }
        allowed = (
            body.get("requester_id") in allowed_requesters
            and body.get("resource") == "quantum-nexus-fusion"
            and body.get("action") == "submit_task"
        )
        result = {"allowed": allowed, "reason": "policy_allow" if allowed else "policy_denied", "policy": "qnf-quantum-submit-v1"}
        print(json.dumps({"event": "qnf_access_check", "caller": caller, **result}, sort_keys=True), flush=True)
        return jsonify(result), 200 if allowed else 403
    @app.get("/v1/fabric/pqc-status")
    def pqc_status():
        ppsim_code, ppsim = _ppsim_status()
        native_verified = ppsim_code == 200 and ppsim.get("mode") == "liboqs_native" and ppsim.get("algorithms", {}).get("kem") == "ML-KEM-1024" and ppsim.get("algorithms", {}).get("signature") == "ML-DSA-87"
        return jsonify({
            "service": "sara-security-fabric", "status": "operational" if native_verified else "degraded", "patch": PATCH_VERSION,
            "suite": {"kem": "ML-KEM-1024", "signature": "ML-DSA-87", "aead": "ChaCha20-Poly1305", "hash": "SHA3-512"},
            "ppsim_url": os.environ.get("SARA_PQC_PPSIM_URL", ""), "ppsim_status": ppsim_code, "ppsim_native_verified": native_verified,
            "rotation_days": int(os.environ.get("SARA_PQC_ROTATION_DAYS", "30")), "rotation_collection": ROTATION_COLLECTION,
            "updated_at_epoch": int(time.time()),
        }), 200 if native_verified else 503

    @app.post("/v1/fabric/pqc-rotate")
    def pqc_rotate():
        ppsim_url = os.environ.get("SARA_PQC_PPSIM_URL", "")
        if not ppsim_url:
            return jsonify({"error": "missing_SARA_PQC_PPSIM_URL"}), 500
        body = request.get_json(silent=True) or {}
        status, payload = _call_json(ppsim_url, "/v1/pqc/rotate-keys", "POST", {"requested_by": body.get("requested_by", "sara-security-fabric"), "reason": body.get("reason", "scheduled_or_manual_rotation")})
        accepted = status == 200 and payload.get("rotated") is True and payload.get("mode") == "liboqs_native"
        if not accepted:
            return jsonify({"service": "sara-security-fabric", "operation": "pqc-rotate", "accepted": False, "ppsim_status": status, "error": payload.get("error", "rotation_not_verified")}), 502
        event = {
            "schema": "sara_pqc_rotation_event_v1", "service": "sara-security-fabric", "operation": "pqc-rotate", "accepted": True,
            "ppsim_url": ppsim_url, "ppsim_patch": payload.get("patch"), "mode": payload.get("mode"), "algorithms": payload.get("algorithms"),
            "secret_versions": payload.get("secret_versions"), "public_keys": payload.get("public_keys"), "requested_by": body.get("requested_by", "sara-security-fabric"),
            "reason": body.get("reason", "scheduled_or_manual_rotation"), "rotated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            event_id = _audit_rotation(event)
        except Exception as exc:
            return jsonify({"service": "sara-security-fabric", "operation": "pqc-rotate", "accepted": False, "error": "rotation_audit_failed", "detail": str(exc)[:300]}), 500
        return jsonify({**event, "event_id": event_id, "private_key_material": "not_returned"}), 200

    return app

