import hashlib
import json
import os
import time
import uuid
from typing import Optional

from fastapi import HTTPException
from google.cloud import firestore
from pydantic import BaseModel, Field

PATCH_VERSION = "SARA-QUANTUM-DEFENSE-ALT-001-IMPL-v1.3"
DATABASE_VERSION = "NIST-PQC-FIPS-203-204-2024"

ALGORITHM_STATUS = {
    "ML-KEM-1024": {
        "decision": "CURRENT",
        "nist_status": "standardized",
        "standard": "FIPS 203",
        "attack_surface": "module_lattice_kem",
        "design_alias": "CRYSTALS-Kyber-1024",
    },
    "ML-DSA-87": {
        "decision": "CURRENT",
        "nist_status": "standardized",
        "standard": "FIPS 204",
        "attack_surface": "module_lattice_signature",
        "design_alias": "CRYSTALS-Dilithium-L5",
    },
    "CRYSTALS-Kyber-1024": {
        "decision": "CURRENT",
        "nist_status": "standardized_as_ML-KEM-1024",
        "standard": "FIPS 203",
        "attack_surface": "module_lattice_kem",
    },
    "CRYSTALS-Dilithium-L5": {
        "decision": "CURRENT",
        "nist_status": "standardized_as_ML-DSA-87",
        "standard": "FIPS 204",
        "attack_surface": "module_lattice_signature",
    },
    "ChaCha20-Poly1305": {
        "decision": "CURRENT",
        "nist_status": "symmetric_aead",
        "standard": "RFC 8439",
        "attack_surface": "grover_reduced_margin_acceptable_with_256_bit_key",
    },
    "SHA3-512": {
        "decision": "CURRENT",
        "nist_status": "hash_standard",
        "standard": "FIPS 202",
        "attack_surface": "grover_margin_512_bit_output",
    },
}


class AlgorithmRequest(BaseModel):
    algorithm: Optional[str] = None
    name: Optional[str] = None
    reason: Optional[str] = None
    recommendation_id: Optional[str] = Field(default=None, max_length=200)


def _canonical(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(data) -> str:
    return hashlib.sha3_512(_canonical(data).encode("utf-8")).hexdigest()


def _collection():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or os.environ.get("PROJECT_ID")
    name = os.environ.get("SARA_QUANTUM_FABRIC_COLLECTION", "sara_crypto_recommendations")
    client = firestore.Client(project=project) if project else firestore.Client()
    return client.collection(name)


def _decision_for(name: str) -> dict:
    normalized = (name or "").strip()
    known = ALGORITHM_STATUS.get(normalized)
    if known:
        return {"algorithm": normalized, **known}
    return {
        "algorithm": normalized or "unknown",
        "decision": "MONITOR",
        "nist_status": "unknown_or_untracked",
        "standard": None,
        "attack_surface": "requires_manual_review",
    }


def _same_recommendation(left: dict, right: dict) -> bool:
    comparable = ("algorithm", "decision", "nist_status", "standard", "reason", "database_version", "patch")
    return all(left.get(key) == right.get(key) for key in comparable)


def _persist_recommendation(entry: dict) -> tuple[dict, bool]:
    ref = _collection().document(entry["recommendation_id"])
    transaction = ref._client.transaction()

    @firestore.transactional
    def create_or_replay(transaction):
        existing = ref.get(transaction=transaction)
        if existing.exists:
            saved = existing.to_dict()
            comparable = ("algorithm", "decision", "nist_status", "standard", "reason", "database_version", "patch")
            if any(saved.get(key) != entry.get(key) for key in comparable):
                raise HTTPException(status_code=409, detail="recommendation_id already exists with different content")
            return saved, False
        transaction.create(ref, entry)
        return entry, True

    return create_or_replay(transaction)


def _storage_status() -> dict:
    docs = list(_collection().order_by("timestamp_epoch", direction=firestore.Query.DESCENDING).limit(1).stream())
    return {
        "reachable": True,
        "latest_recommendation_id": docs[0].id if docs else None,
    }


def register_quantum_fabric(app):
    @app.post("/v1/quantum/assess-algorithm")
    def assess_algorithm(body: AlgorithmRequest):
        name = body.algorithm or body.name or ""
        return {
            "service": "sara-evolution-engine",
            "patch": PATCH_VERSION,
            "assessment": _decision_for(name),
            "source": "versioned_nist_pqc_and_quantum_attack_database",
            "database_version": DATABASE_VERSION,
            "external_api_calls": False,
        }

    @app.get("/v1/quantum/fabric-status")
    def fabric_status():
        try:
            storage = _storage_status()
        except Exception as exc:
            storage = {"reachable": False, "error": type(exc).__name__}
        return {
            "service": "sara-evolution-engine",
            "status": "operational" if storage["reachable"] else "degraded",
            "patch": PATCH_VERSION,
            "database_version": DATABASE_VERSION,
            "suite": ALGORITHM_STATUS,
            "ppsim_url_configured": bool(os.environ.get("SARA_PQC_PPSIM_URL", "")),
            "recommendation_collection": os.environ.get("SARA_QUANTUM_FABRIC_COLLECTION", "sara_crypto_recommendations"),
            "persistence": storage,
        }

    @app.post("/v1/quantum/recommend-update")
    def recommend_update(body: AlgorithmRequest):
        assessment = _decision_for(body.algorithm or body.name or "")
        recommendation_id = body.recommendation_id or "QREC-" + uuid.uuid4().hex
        unsigned = {
            "recommendation_id": recommendation_id,
            "timestamp_epoch": int(time.time()),
            "algorithm": assessment["algorithm"],
            "decision": assessment["decision"],
            "nist_status": assessment["nist_status"],
            "standard": assessment["standard"],
            "reason": body.reason or assessment["attack_surface"],
            "database_version": DATABASE_VERSION,
            "patch": PATCH_VERSION,
        }
        entry = {**unsigned, "entry_hash_sha3_512": _hash(unsigned)}
        try:
            saved, created = _persist_recommendation(entry)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"recommendation was not persisted: {exc}") from exc
        return {"accepted": True, "persisted": True, "created": created, **saved}

    return app



