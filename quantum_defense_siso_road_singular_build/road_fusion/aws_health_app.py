from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

try:
    from .claim_policy import SUPPORTED_SCOPE_LIMITED_CLAIM, evaluate_claims, policy_manifest
    from .road_gate import road_status
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from claim_policy import SUPPORTED_SCOPE_LIMITED_CLAIM, evaluate_claims, policy_manifest
    from road_gate import road_status


SERVICE = "sara-quantum-defense-road-fusion"


def _json(payload: dict, status: int = 200) -> tuple[int, dict[str, str], str]:
    payload.setdefault("service", SERVICE)
    return status, {"content-type": "application/json"}, json.dumps(payload, sort_keys=True)


def route_request(path: str) -> tuple[int, dict[str, str], str]:
    normalized = "/" + path.strip("/")
    if normalized == "/health":
        release = road_status()
        return _json({"status": "healthy" if release["local"] == "PASS" else "blocked", "release": release})
    if normalized == "/road/health":
        release = road_status()
        return _json({"status": "blocked" if release["release"] != "PASS" else "healthy", "release": release})
    if normalized == "/road/status":
        return _json(road_status())
    if normalized == "/road/claims":
        claims = [
            "SARA can defeat all rogue AI.",
            "SARA disables outside AI systems.",
            "SARA has FIPS validation.",
            SUPPORTED_SCOPE_LIMITED_CLAIM,
        ]
        return _json({"status": "healthy", "claims": evaluate_claims(claims, evidence={}), "policy": policy_manifest()})
    return _json({"status": "not_found", "path": normalized}, status=404)


def lambda_handler(event: dict, context: object | None = None) -> dict:
    path = event.get("rawPath") or event.get("path") or "/health"
    status, headers, body = route_request(path)
    return {"statusCode": status, "headers": headers, "body": body}


def wsgi_app(environ: dict, start_response: Callable) -> list[bytes]:
    path = environ.get("PATH_INFO", "/health")
    status, headers, body = route_request(path)
    reason = "OK" if status == 200 else "Not Found"
    start_response(f"{status} {reason}", list(headers.items()))
    return [body.encode("utf-8")]


application = wsgi_app
