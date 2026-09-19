import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, HTTPException
from google.cloud import firestore
from pydantic import BaseModel, Field

PATCH_VERSION = "SARA-QUANTUM-DEFENSE-ALT-001-IMPL-v1.3"
SIGNATURE_ALGORITHM = "ML-DSA-87"
MAX_CHAIN_LIMIT = 100
router = APIRouter(prefix="/v1/integrity", tags=["quantum-integrity"])

class SignStateRequest(BaseModel):
    state: Any
    operation_id: str = Field(min_length=1, max_length=200)

class VerifyStateRequest(BaseModel):
    state: Any
    signature: str = Field(min_length=1)
    public_key: str | None = None

def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

def _sha3(data: Any) -> str:
    return hashlib.sha3_512(_canonical(data).encode("utf-8")).hexdigest()

def _project_id() -> str | None:
    return os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or os.environ.get("PROJECT_ID")

def _collection():
    name = os.environ.get("SARA_INTEGRITY_CHAIN_COLLECTION", "sara_integrity_chain")
    project = _project_id()
    client = firestore.Client(project=project) if project else firestore.Client()
    return client.collection(name)

def _identity_token(audience: str) -> str:
    url = ("http://metadata.google.internal/computeMetadata/v1/instance/"
           "service-accounts/default/identity?audience=" + urllib.parse.quote(audience.rstrip("/"), safe=""))
    request = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(request, timeout=10) as response:
        token = response.read().decode("utf-8").strip()
    if not token:
        raise RuntimeError("metadata server returned an empty identity token")
    return token

def _call_ppsim(path: str, body: dict[str, Any]) -> dict[str, Any]:
    base_url = os.environ.get("SARA_PQC_PPSIM_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("SARA_PQC_PPSIM_URL is not configured")
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={"Authorization": "Bearer " + _identity_token(base_url), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PPSIM returned HTTP {exc.code}: {detail}") from exc
    if payload.get("algorithm") != SIGNATURE_ALGORITHM:
        raise RuntimeError(f"PPSIM algorithm mismatch: {payload.get('algorithm')!r}")
    if payload.get("mode") != "liboqs_native":
        raise RuntimeError(f"PPSIM is not native: {payload.get('mode')!r}")
    return payload

def _safe_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: entry.get(key) for key in (
        "operation_id", "sequence", "timestamp_epoch", "state_hash_sha3_512",
        "entry_hash_sha3_512", "previous_entry_hash_sha3_512",
        "signature_algorithm", "signature_mode", "patch"
    )}

class OperationConflict(Exception):
    pass

def _append_entry(operation_id: str, state_hash: str, signature: str, public_key: str) -> tuple[dict[str, Any], bool]:
    collection = _collection()
    entry_ref = collection.document(operation_id)
    head_ref = collection.document("_head")
    transaction = collection._client.transaction()

    @firestore.transactional
    def append(transaction):
        existing = entry_ref.get(transaction=transaction)
        if existing.exists:
            entry = existing.to_dict()
            if entry.get("state_hash_sha3_512") != state_hash:
                raise OperationConflict("operation_id already exists for a different state")
            return entry, False
        head_snapshot = head_ref.get(transaction=transaction)
        head = head_snapshot.to_dict() if head_snapshot.exists else {}
        sequence = int(head.get("sequence", 0)) + 1
        unsigned_entry = {
            "operation_id": operation_id,
            "sequence": sequence,
            "timestamp_epoch": int(time.time()),
            "state_hash_sha3_512": state_hash,
            "previous_entry_hash_sha3_512": str(head.get("entry_hash_sha3_512", "")),
            "signature": signature,
            "public_key": public_key,
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "signature_mode": "liboqs_native",
            "patch": PATCH_VERSION,
        }
        entry = {**unsigned_entry, "entry_hash_sha3_512": _sha3(unsigned_entry)}
        transaction.create(entry_ref, entry)
        transaction.set(head_ref, {
            "sequence": sequence,
            "entry_hash_sha3_512": entry["entry_hash_sha3_512"],
            "operation_id": operation_id,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        return entry, True
    return append(transaction)

@router.post("/sign-state")
def sign_state(body: SignStateRequest):
    if body.operation_id == "_head":
        raise HTTPException(status_code=422, detail="operation_id is reserved")
    state_hash = _sha3(body.state)
    try:
        existing = _collection().document(body.operation_id).get()
        if existing.exists:
            entry = existing.to_dict()
            if entry.get("state_hash_sha3_512") != state_hash:
                raise HTTPException(status_code=409, detail="operation_id already exists for a different state")
            return {"accepted": True, "created": False, **entry}
        signed = _call_ppsim("/v1/pqc/sign", {"message": state_hash})
        signature = str(signed.get("signature") or "")
        public_key = str(signed.get("public_key") or "")
        if not signature or not public_key:
            raise RuntimeError("PPSIM did not return signature and public key")
        entry, created = _append_entry(body.operation_id, state_hash, signature, public_key)
        return {"accepted": True, "created": created, **entry}
    except HTTPException:
        raise
    except OperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"integrity state was not persisted: {exc}") from exc

@router.post("/verify-state")
def verify_state(body: VerifyStateRequest):
    state_hash = _sha3(body.state)
    payload: dict[str, Any] = {"message": state_hash, "signature": body.signature}
    if body.public_key:
        payload["public_key"] = body.public_key
    try:
        verified = _call_ppsim("/v1/pqc/verify", payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"PPSIM verification failed: {exc}") from exc
    return {
        "valid": bool(verified.get("valid")),
        "state_hash_sha3_512": state_hash,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_mode": "liboqs_native",
        "patch": PATCH_VERSION,
    }

@router.get("/chain")
def chain(limit: int = 25):
    if limit < 1 or limit > MAX_CHAIN_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_CHAIN_LIMIT}")
    try:
        docs = (_collection().where("sequence", ">", 0)
                .order_by("sequence", direction=firestore.Query.DESCENDING)
                .limit(limit + 1).stream())
        entries = [_safe_entry(doc.to_dict()) for doc in docs if doc.id != "_head"][:limit]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"integrity chain unavailable: {exc}") from exc
    return {
        "service": "sara-global-truth-protocol",
        "status": "operational",
        "patch": PATCH_VERSION,
        "append_only": True,
        "raw_state_returned": False,
        "entries": entries,
    }


