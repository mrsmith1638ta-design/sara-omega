from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_CREDENTIAL_KEY_PARTS = (
    "authorization",
    "bearer",
    "client_secret",
    "oauth_token",
    "owner_token",
    "piper_service_token",
)
_INTERNAL_IDENTITY_KEYS = {"tenant_id", "user_uuid"}
_RAW_TRANSCRIPT_KEYS = {"raw_transcript", "transcript", "transcript_text"}


def _file_record(path_value: str) -> dict[str, str]:
    path = Path(path_value)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _contains_private_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://") or ".internal" in lowered


def _validate_evidence_value(
    value: Any,
    *,
    sensitive_values: tuple[str, ...],
) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            if lowered in _INTERNAL_IDENTITY_KEYS:
                raise ValueError("internal identity is not permitted in Voice 1.1A evidence")
            if lowered in _RAW_TRANSCRIPT_KEYS or any(
                part in lowered for part in _CREDENTIAL_KEY_PARTS
            ):
                raise ValueError("sensitive evidence key is not permitted")
            _validate_evidence_value(nested, sensitive_values=sensitive_values)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            _validate_evidence_value(nested, sensitive_values=sensitive_values)
        return
    if isinstance(value, str):
        if _contains_private_url(value):
            raise ValueError("private URL is not permitted in Voice 1.1A evidence")
        if any(secret and secret in value for secret in sensitive_values):
            raise ValueError("sensitive evidence value is not permitted")


def build_voice_1_1a_evidence(
    *,
    voice_1_0_paths: list[str],
    voice_1_1_paths: list[str],
    source_commit_sha: str,
    sara_deployment_id: str,
    piper_deployment_id: str,
    transaction: dict,
    entitlement: dict,
    isolation: dict,
    limits: dict,
    privacy: dict,
    restart: dict,
    road: dict,
    sensitive_values: list[str] | None = None,
) -> dict[str, Any]:
    if not _COMMIT_PATTERN.fullmatch(source_commit_sha):
        raise ValueError("source_commit_sha must be 40 lowercase hexadecimal characters")
    if not sara_deployment_id.strip() or not piper_deployment_id.strip():
        raise ValueError("deployment identifiers are required")
    sections = {
        "transaction": transaction,
        "entitlement": entitlement,
        "isolation": isolation,
        "limits": limits,
        "privacy": privacy,
        "restart": restart,
        "road": road,
    }
    _validate_evidence_value(
        sections,
        sensitive_values=tuple(item for item in (sensitive_values or []) if item),
    )
    return {
        "evidence_type": "sara-omega-voice-1-1a-acceptance",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "immutable_baselines": {
            "voice_1_0": [_file_record(path) for path in sorted(voice_1_0_paths)],
            "voice_1_1": [_file_record(path) for path in sorted(voice_1_1_paths)],
        },
        "voice_1_1a": {
            "source_commit_sha": source_commit_sha,
            "sara_deployment_id": sara_deployment_id,
            "piper_deployment_id": piper_deployment_id,
            **sections,
        },
        "records_sensitive_values": False,
    }
