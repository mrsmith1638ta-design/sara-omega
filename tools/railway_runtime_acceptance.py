#!/usr/bin/env python3
"""Run the live SARA-OMEGA V.3.2 Railway acceptance checks.

Usage:
  SARA_OWNER_TOKEN='...' python tools/railway_runtime_acceptance.py https://service.up.railway.app

The script never prints tokens. Restore is intentionally opt-in because it mutates
live runtime state.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlparse

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--exercise-restore", action="store_true")
    parser.add_argument("--require-gpt-action-token", action="store_true")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("base_url must be an HTTPS service URL")

    owner_token = os.environ.get("SARA_OWNER_TOKEN", "").strip()
    if not owner_token:
        raise SystemExit("SARA_OWNER_TOKEN is required in the environment")
    gpt_action_token = os.environ.get("SARA_GPT_ACTION_TOKEN", "").strip()

    auth = {"Authorization": f"Bearer {owner_token}"}
    action_auth = {"Authorization": f"Bearer {gpt_action_token}"} if gpt_action_token else None
    report = {"base_url": base_url, "checks": []}
    failed = False

    def check(method: str, path: str, *, headers=None, json_body=None, expected=(200,)):
        nonlocal failed
        response = client.request(method, base_url + path, headers=headers, json=json_body)
        ok = response.status_code in expected
        item = {"method": method, "path": path, "status": response.status_code, "ok": ok}
        try:
            item["body"] = response.json()
        except ValueError:
            item["body"] = response.text[:500]
        report["checks"].append(item)
        if not ok:
            failed = True
        return response, item

    with httpx.Client(timeout=args.timeout, follow_redirects=False) as client:
        check("GET", "/")
        check("GET", "/health")
        check("GET", "/health/live")
        ready_response, _ = check("GET", "/health/ready")
        acceptance_response, acceptance = check("GET", "/health/production-acceptance")
        check("GET", "/admin/failsafe/status", headers=auth)
        check("GET", "/admin/production-acceptance", headers=auth)
        checkpoint_response, _ = check("POST", "/admin/failsafe/checkpoint", headers=auth)
        if args.exercise_restore and checkpoint_response.status_code == 200:
            check("POST", "/admin/failsafe/restore-latest", headers=auth)
        if action_auth:
            check(
                "POST",
                "/gpt/action/gateway",
                headers=action_auth,
                json_body={"operation": "status"},
            )
            check("GET", "/admin/stats", headers=action_auth, expected=(403,))
            verify_response, verify_item = check(
                "POST",
                "/gpt/action/gateway",
                headers=action_auth,
                json_body={
                    "operation": "verify_output",
                    "module": "railway-acceptance",
                    "output": "sara-module-registry is live.",
                    "context": {
                        "live_module_truth": {
                            "sara-module-registry": {
                                "live": False,
                                "source": "railway-runtime-acceptance",
                            }
                        }
                    },
                },
            )
            if verify_response.status_code == 200:
                body = verify_item.get("body") or {}
                if not isinstance(body, dict) or body.get("verdict") != "BLOCK":
                    failed = True
                    report["checks"].append({
                        "method": "ASSERT",
                        "path": "/gpt/action/gateway",
                        "ok": False,
                        "reason": "GPT Action token verify_output did not fail closed on false live-module claim",
                    })
        elif args.require_gpt_action_token:
            failed = True
            report["checks"].append({
                "method": "ASSERT",
                "path": "Railway GPT_ACTION_TOKEN",
                "ok": False,
                "reason": "SARA_GPT_ACTION_TOKEN is required to verify the dedicated GPT Action boundary",
            })

        if acceptance_response.status_code == 200:
            body = acceptance.get("body") or {}
            if not isinstance(body, dict) or not body.get("production_accepted"):
                failed = True
                report["checks"].append({
                    "method": "ASSERT",
                    "path": "/health/production-acceptance",
                    "ok": False,
                    "reason": "production_accepted is not true; a second boot may be required for persistence proof",
                })
        if ready_response.status_code != 200:
            failed = True

    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
