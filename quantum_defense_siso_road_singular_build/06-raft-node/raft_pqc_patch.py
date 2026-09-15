import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from flask import jsonify, request
from google.cloud import firestore

PATCH_VERSION = "SARA-QUANTUM-DEFENSE-ALT-001-IMPL-v1.3"
SIGNATURE_ALGORITHM = "ML-DSA-87"
QUORUM_SIZE = int(os.environ.get("SARA_PQC_QUORUM_SIZE", "2"))
LEDGER_COLLECTION = os.environ.get("SARA_PQC_LEDGER_COLLECTION", "sara_pqc_consensus_proposals")
_ACCEPTED_VOTES = []
_SEEN_VOTE_HASHES = set()
_FIRESTORE_CLIENT = None


def _canonical(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _vote_hash(vote) -> str:
    return hashlib.sha3_512(_canonical(vote).encode("utf-8")).hexdigest()


def _identity_token(audience: str) -> str:
    url = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/identity?audience="
        + urllib.parse.quote(audience.rstrip("/"), safe="")
    )
    req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        token = resp.read().decode("utf-8").strip()
    if not token:
        raise RuntimeError("metadata server returned an empty identity token")
    return token


def _verify_signature(message: str, signature: str, public_key: str | None = None) -> dict:
    base_url = os.environ.get("SARA_PQC_PPSIM_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("SARA_PQC_PPSIM_URL is not configured")
    payload = {"message": message, "signature": signature}
    if public_key:
        payload["public_key"] = public_key
    req = urllib.request.Request(
        base_url + "/v1/pqc/verify",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + _identity_token(base_url),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PPSIM returned HTTP {exc.code}: {detail}") from exc
    if result.get("algorithm") != SIGNATURE_ALGORITHM:
        raise RuntimeError(f"PPSIM algorithm mismatch: {result.get('algorithm')!r}")
    if result.get("mode") != "liboqs_native":
        raise RuntimeError(f"PPSIM is not native: {result.get('mode')!r}")
    return result


def _strict() -> bool:
    return os.environ.get("SARA_PQC_CONSENSUS_STRICT", "true").lower() == "true"



def _firestore_client():
    global _FIRESTORE_CLIENT
    if _FIRESTORE_CLIENT is None:
        _FIRESTORE_CLIENT = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT"))
    return _FIRESTORE_CLIENT


def _proposal_id(vote: dict) -> str:
    value = str(vote.get("proposal_id") or "").strip()
    if not value:
        raise ValueError("proposal_id_required")
    return value


def _record_verified_vote_impl(transaction, proposal_ref, entry):
    snapshot = proposal_ref.get(transaction=transaction)
    data = snapshot.to_dict() or {}
    expected_hash = data.get("vote_hash_sha3_512")
    if expected_hash and expected_hash != entry["vote_hash_sha3_512"]:
        raise ValueError("proposal_vote_hash_conflict")
    votes = dict(data.get("votes") or {})
    if entry["node_id"] in votes:
        return {"duplicate": True, "committed": bool(data.get("committed")), "quorum_count": len(votes), "attested_nodes": sorted(votes)}
    votes[entry["node_id"]] = entry
    nodes = sorted(votes)
    committed = len(nodes) >= QUORUM_SIZE
    update = {
        "proposal_id": entry["proposal_id"],
        "vote_hash_sha3_512": entry["vote_hash_sha3_512"],
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_mode": "liboqs_native",
        "quorum_required": QUORUM_SIZE,
        "quorum_count": len(nodes),
        "attested_nodes": nodes,
        "votes": votes,
        "committed": committed,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    if not snapshot.exists:
        update["created_at"] = firestore.SERVER_TIMESTAMP
    if committed and not data.get("committed"):
        update["committed_at"] = firestore.SERVER_TIMESTAMP
    transaction.set(proposal_ref, update, merge=True)
    return {"duplicate": False, "committed": committed, "quorum_count": len(nodes), "attested_nodes": nodes}


_record_verified_vote = firestore.transactional(_record_verified_vote_impl)


def _persist_verified_vote(entry: dict) -> dict:
    client = _firestore_client()
    ref = client.collection(LEDGER_COLLECTION).document(entry["proposal_id"])
    return _record_verified_vote(client.transaction(), ref, entry)

def register_raft_pqc(app):
    @app.get("/v1/consensus/pqc-status")
    def pqc_status():
        return jsonify({
            "service": os.environ.get("K_SERVICE", "raft-node"),
            "node_id": os.environ.get("NODE_ID", ""),
            "status": "operational",
            "patch": PATCH_VERSION,
            "pqc_consensus_strict": _strict(),
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "signature_mode": "liboqs_native_required",
            "ppsim_configured": bool(os.environ.get("SARA_PQC_PPSIM_URL", "")),
            "accepted_vote_count_ephemeral": len(_ACCEPTED_VOTES),
            "durable_vote_ledger": True,
            "durable_vote_backend": "firestore",
            "ledger_collection": LEDGER_COLLECTION,
            "quorum_required": QUORUM_SIZE,
        })

    def _handle_pqc_vote(source: str):
        body = request.get_json(silent=True) or {}
        vote = body.get("vote")
        if not isinstance(vote, dict) or not vote:
            return jsonify({"accepted": False, "reason": "vote_object_required"}), 422
        signature = str(body.get("signature") or "")
        public_key = str(body.get("public_key") or "") or None
        canonical_vote = _canonical(vote)
        digest = _vote_hash(vote)
        try:
            proposal_id = _proposal_id(vote)
        except ValueError as exc:
            return jsonify({"accepted": False, "reason": str(exc)}), 422

        if signature:
            try:
                verified = _verify_signature(canonical_vote, signature, public_key)
            except Exception as exc:
                return jsonify({"accepted": False, "reason": "pqc_verification_unavailable", "detail": str(exc)}), 503
            if not bool(verified.get("valid")):
                return jsonify({"accepted": False, "reason": "invalid_pqc_signature"}), 403
            verification = {"valid": True, "algorithm": SIGNATURE_ALGORITHM, "mode": "liboqs_native"}
        elif _strict():
            return jsonify({"accepted": False, "reason": "missing_pqc_signature_strict_mode"}), 403
        else:
            return jsonify({"accepted": False, "reason": "missing_pqc_signature"}), 403

        if digest in _SEEN_VOTE_HASHES:
            return jsonify({"accepted": False, "reason": "duplicate_vote", "vote_hash_sha3_512": digest}), 409

        entry = {
            "node_id": os.environ.get("NODE_ID", ""),
            "timestamp_epoch": int(time.time()),
            "signed": bool(signature),
            "vote_hash_sha3_512": digest,
            "vote_term": vote.get("term"),
            "candidate_id": vote.get("candidate_id"),
            "proposal_id": proposal_id,
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "signature_mode": "liboqs_native",
            "source": source,
        }
        try:
            ledger = _persist_verified_vote(entry)
        except ValueError as exc:
            return jsonify({"accepted": False, "reason": str(exc)}), 409
        except Exception as exc:
            return jsonify({"accepted": False, "reason": "durable_vote_write_failed", "detail": type(exc).__name__}), 503
        if ledger.get("duplicate"):
            return jsonify({"accepted": False, "reason": "duplicate_node_vote", "vote_hash_sha3_512": digest, "quorum": ledger}), 409
        _SEEN_VOTE_HASHES.add(digest)
        _ACCEPTED_VOTES.append(entry)
        del _ACCEPTED_VOTES[:-100]
        return jsonify({
            "accepted": True,
            "strict": _strict(),
            "verification": verification,
            "entry": entry,
            "quorum": ledger,
            "raw_vote_returned": False,
        })

    @app.post("/v1/consensus/pqc-vote")
    def pqc_vote():
        return _handle_pqc_vote("pqc-vote")

    @app.get("/v1/consensus/pqc-commit/<proposal_id>")
    def pqc_commit(proposal_id: str):
        snapshot = _firestore_client().collection(LEDGER_COLLECTION).document(proposal_id).get()
        if not snapshot.exists:
            return jsonify({"proposal_id": proposal_id, "committed": False, "quorum_count": 0, "quorum_required": QUORUM_SIZE}), 404
        data = snapshot.to_dict() or {}
        return jsonify({
            "proposal_id": proposal_id,
            "committed": bool(data.get("committed")),
            "quorum_count": int(data.get("quorum_count", 0)),
            "quorum_required": int(data.get("quorum_required", QUORUM_SIZE)),
            "attested_nodes": data.get("attested_nodes", []),
            "vote_hash_sha3_512": data.get("vote_hash_sha3_512"),
            "signature_algorithm": data.get("signature_algorithm"),
            "signature_mode": data.get("signature_mode"),
            "durable_vote_ledger": True,
        })

    return app
