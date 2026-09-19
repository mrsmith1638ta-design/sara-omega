from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def _file_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_acceptance_evidence(
    *,
    voice_1_0_capsule: str,
    source_commit_sha: str,
    deployment_id: str,
    job_receipt: dict,
    benchmark: dict,
    restart_persistence: dict,
    road: dict,
) -> dict:
    return {
        "evidence_type": "sara-omega-voice-1-1-acceptance",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "voice_1_0_capsule": voice_1_0_capsule,
        "voice_1_0_capsule_sha256": _file_sha256(voice_1_0_capsule),
        "voice_1_1": {
            "source_commit_sha": source_commit_sha,
            "deployment_id": deployment_id,
            "job_receipt": job_receipt,
            "benchmark": benchmark,
            "restart_persistence": restart_persistence,
            "road": road,
        },
        "records_sensitive_values": False,
    }
