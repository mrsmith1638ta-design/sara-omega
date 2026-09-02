from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "custom-gpt-action-sync-report.json"
DEFAULT_SCHEMA_URL = "https://sara-omega-production.up.railway.app/gpt/action/openapi.yaml"
GITHUB_RUNS_URL = (
    "https://api.github.com/repos/mrsmith1638ta-design/sara-omega/actions/runs"
    "?branch=main&per_page=10"
)
REQUIRED_OPERATION_IDS = {
    "getSaraOmegaIdentity",
    "getSaraOmegaReadiness",
    "getSaraOmegaProductionAcceptance",
    "getContextDevAuthorizationStatus",
    "saraOmegaGovernedGateway",
}
REQUIRED_GATEWAY_OPERATIONS = {
    "status",
    "production_acceptance",
    "module_awareness",
    "runtime_assurance",
    "concentration",
    "hawkins_chaos",
    "titan_health",
    "solve",
    "verify_output",
}


def normalize_schema(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()


def fetch_text(url: str, timeout: int = 30) -> tuple[int | None, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "sara-omega-sync-resolver/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace"), ""
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), str(exc)
    except Exception as exc:
        return None, "", str(exc)


def operation_ids(schema: str) -> set[str]:
    return set(re.findall(r"^\s*operationId:\s*([A-Za-z0-9_]+)\s*$", schema, flags=re.MULTILINE))


def gateway_operations(schema: str) -> set[str]:
    values = set(re.findall(r"^\s*-\s*([a-z][a-z0-9_]+)\s*$", schema, flags=re.MULTILINE))
    return values & REQUIRED_GATEWAY_OPERATIONS


def validate_schema_contract(schema: str) -> dict[str, Any]:
    ops = operation_ids(schema)
    gateway_ops = gateway_operations(schema)
    missing_operation_ids = sorted(REQUIRED_OPERATION_IDS - ops)
    missing_gateway_operations = sorted(REQUIRED_GATEWAY_OPERATIONS - gateway_ops)
    failures = []
    if "openapi: 3.1.0" not in schema:
        failures.append("schema_not_openapi_3_1_0")
    if "https://sara-omega-production.up.railway.app" not in schema:
        failures.append("production_server_missing")
    if "bearerAuth" not in schema or "scheme: bearer" not in schema:
        failures.append("bearer_auth_missing")
    if missing_operation_ids:
        failures.append("missing_operation_ids")
    if missing_gateway_operations:
        failures.append("missing_gateway_operations")

    return {
        "pass": not failures,
        "failures": failures,
        "operation_ids": sorted(ops),
        "gateway_operations": sorted(gateway_ops),
        "missing_operation_ids": missing_operation_ids,
        "missing_gateway_operations": missing_gateway_operations,
    }


def latest_github_validation() -> dict[str, Any]:
    status, body, error = fetch_text(GITHUB_RUNS_URL, timeout=20)
    if status != 200:
        return {
            "name": "github_validation_database",
            "pass": False,
            "status": "unavailable",
            "http_status": status,
            "error": error,
        }

    payload = json.loads(body)
    runs = payload.get("workflow_runs", [])
    validation_runs = [
        run for run in runs if run.get("name") == "SARA-OMEGA V3.2.1 validation"
    ]
    latest = validation_runs[0] if validation_runs else None
    if not latest:
        return {
            "name": "github_validation_database",
            "pass": False,
            "status": "missing",
            "reason": "No SARA-OMEGA V3.2.1 validation run found on main.",
        }

    return {
        "name": "github_validation_database",
        "pass": latest.get("status") == "completed" and latest.get("conclusion") == "success",
        "status": latest.get("status"),
        "conclusion": latest.get("conclusion"),
        "run_id": latest.get("id"),
        "head_sha": latest.get("head_sha"),
        "title": latest.get("display_title"),
        "url": latest.get("html_url"),
        "created_at": latest.get("created_at"),
        "updated_at": latest.get("updated_at"),
    }


def git_object_database() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "fsck", "--full", "--strict"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "name": "git_object_database",
            "pass": False,
            "status": "blocked",
            "reason": str(exc),
        }

    return {
        "name": "git_object_database",
        "pass": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }


def resolve_sync(schema_url: str = DEFAULT_SCHEMA_URL, include_github: bool = True) -> dict[str, Any]:
    local_schema = normalize_schema((ROOT / "chatgpt-gpt-action.yaml").read_text(encoding="utf-8"))
    local_contract = validate_schema_contract(local_schema)

    live_status, live_schema_raw, live_error = fetch_text(schema_url)
    live_schema = normalize_schema(live_schema_raw) if live_schema_raw else ""
    live_contract = validate_schema_contract(live_schema) if live_schema else {
        "pass": False,
        "failures": ["live_schema_unavailable"],
        "operation_ids": [],
        "gateway_operations": [],
        "missing_operation_ids": sorted(REQUIRED_OPERATION_IDS),
        "missing_gateway_operations": sorted(REQUIRED_GATEWAY_OPERATIONS),
    }

    schema_match = bool(live_schema) and local_schema == live_schema
    checks = [
        {
            "name": "local_openapi_contract",
            **local_contract,
        },
        {
            "name": "live_openapi_contract",
            "pass": live_status == 200 and live_contract["pass"],
            "http_status": live_status,
            "error": live_error,
            **live_contract,
        },
        {
            "name": "local_live_schema_match",
            "pass": schema_match,
            "local_length": len(local_schema),
            "live_length": len(live_schema),
        },
        git_object_database(),
    ]
    if include_github:
        checks.append(latest_github_validation())

    resolver_ready = all(check.get("pass") for check in checks)
    return {
        "project": "SARA-OMEGA V3.2.1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "schema_url": schema_url,
        "resolver_ready": resolver_ready,
        "custom_gpt_editor_sync": {
            "status": "manual_import_required" if resolver_ready else "blocked",
            "reason": (
                "Browser automation is unavailable; import must be completed in the ChatGPT GPT editor."
                if resolver_ready
                else "One or more resolver gates failed before the GPT editor import."
            ),
            "authentication": {
                "type": "API key",
                "auth_type": "Bearer",
                "secret_source": "Railway GPT_ACTION_TOKEN, or TEST_TOKEN as a limited fallback. Do not use OWNER_TOKEN for shared GPTs.",
            },
            "action_to_test": "saraOmegaGovernedGateway",
        },
        "editor_import_package": {
            "openapi_schema_url": schema_url,
            "action_gateway_url": "https://sara-omega-production.up.railway.app/gpt/action/gateway",
            "required_manual_steps": [
                "Open the production SARA GPT editor.",
                "Create or replace the SARA-OMEGA Action.",
                "Import the hosted OpenAPI schema URL.",
                "Set authentication to API key with Bearer auth.",
                "Paste the governed Railway token only into the editor secret field.",
                "Use Preview/Test to call saraOmegaGovernedGateway with operation=status.",
                "Then test verify_output with a false live-module claim and confirm fail-closed suppression.",
            ],
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve Custom GPT Action sync readiness.")
    parser.add_argument("--schema-url", default=DEFAULT_SCHEMA_URL)
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)

    report = resolve_sync(schema_url=args.schema_url, include_github=not args.skip_github)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["resolver_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
