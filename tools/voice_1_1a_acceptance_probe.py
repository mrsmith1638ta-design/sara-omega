from __future__ import annotations

import hashlib
import ipaddress
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_CREDENTIAL_KEY_PARTS = (
    "access_token",
    "api_key",
    "authorization",
    "bearer",
    "client_secret",
    "credential",
    "oauth_token",
    "owner_token",
    "password",
    "piper_service_token",
    "refresh_token",
    "secret",
)
_INTERNAL_IDENTITY_KEYS = {"actor", "internal_id", "subject", "tenant_id", "user_uuid"}
_RAW_TRANSCRIPT_KEYS = {"raw_transcript", "transcript", "transcript_text"}
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_BEARER_PATTERN = re.compile(r"\bBearer\s+\S+", re.IGNORECASE)


def _file_record(path_value: str) -> dict[str, str]:
    path = Path(path_value)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _contains_private_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        if parsed.scheme not in {"http", "https"} or hostname is None:
            return False
        lowered = hostname.lower()
        if parsed.scheme == "http" or lowered == "localhost" or lowered.endswith(".internal"):
            return True
        try:
            address = ipaddress.ip_address(lowered)
        except ValueError:
            return False
        return not address.is_global
    except ValueError:
        return True


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
        if _BEARER_PATTERN.search(value):
            raise ValueError("credential value is not permitted in Voice 1.1A evidence")
        if _UUID_PATTERN.search(value):
            raise ValueError("raw identity value is not permitted in Voice 1.1A evidence")
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
