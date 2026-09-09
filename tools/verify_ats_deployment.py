#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from urllib.request import Request, urlopen


def fetch(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "sara-ats-deployment-verifier/1"})
    with urlopen(req, timeout=20) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://sara-omega-production.up.railway.app")
    ap.add_argument("--expected-commit", required=True)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    health = fetch(base + "/ats-intelligence/health")
    att = fetch(base + "/ats-intelligence/attestation")
    prod = fetch(base + "/health/production-acceptance")
    checks = {
        "module_present": health.get("module") == "sara-ats-intelligence" and health.get("present") is True,
        "store_ready": health.get("store_ready") is True,
        "separate_mutation_authority": health.get("mutation_authority_separate") is True,
        "truth_preserving": att.get("truth_preserving_tailoring") is True,
        "bu_isolation": att.get("business_unit_scope_isolation") is True,
        "stale_suppression": att.get("stale_rule_suppression") is True,
        "dynamic_vendor_overlays": att.get("dynamic_vendor_overlays") is True,
        "profile_freshness_fail_closed": att.get("profile_freshness_fail_closed") is True,
        "uncertain_mutation_no_retry": att.get("uncertain_mutation_no_retry") is True,
        "no_execution_authority": att.get("execution_authority") is False,
        "exact_commit": str(att.get("git_commit", "")).lower().startswith(args.expected_commit.lower()),
        "production_accepted": prod.get("production_accepted") is True,
    }
    print(json.dumps({"status": "PASS" if all(checks.values()) else "BLOCKED", "checks": checks, "health": health, "attestation": att}, indent=2))
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
