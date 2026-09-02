from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "local-acceptance-report.json"


def run(command: list[str], timeout: int = 120) -> dict:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    except FileNotFoundError as exc:
        return {"command": command, "returncode": 127, "stderr": str(exc), "stdout": ""}


def sqlite_integrity(db_path: Path) -> dict:
    if not db_path.exists():
        return {
            "name": "sqlite_integrity",
            "path": str(db_path.relative_to(ROOT)),
            "status": "missing",
            "pass": True,
            "reason": "database is created lazily at runtime",
        }

    with closing(sqlite3.connect(db_path)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        decision_count = (
            conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            if "decisions" in tables
            else None
        )

    return {
        "name": "sqlite_integrity",
        "path": str(db_path.relative_to(ROOT)),
        "integrity": integrity,
        "tables": tables,
        "decision_count": decision_count,
        "pass": integrity == "ok",
    }


def docker_build() -> dict:
    docker = shutil.which("docker")
    if not docker:
        return {
            "name": "docker_build",
            "pass": False,
            "status": "blocked",
            "reason": "docker executable is not installed or not on PATH",
            "required_in": "GitHub hosted validation or a machine with Docker Desktop/Engine",
        }

    result = run([docker, "build", "--pull", "-t", "sara-omega:v3.2.1", "."], timeout=900)
    return {
        "name": "docker_build",
        "pass": result["returncode"] == 0,
        "status": "passed" if result["returncode"] == 0 else "failed",
        "result": result,
    }


def main() -> int:
    python = sys.executable
    checks = []

    focused_tests = run(
        [
            python,
            "-m",
            "pytest",
            "tests/test_data_analytics.py",
            "tests/test_memory_database.py",
            "tests/test_runtime_assurance.py",
            "-q",
        ]
    )
    checks.append(
        {
            "name": "datasets_and_databases_pytest",
            "pass": focused_tests["returncode"] == 0,
            "result": focused_tests,
        }
    )

    checks.append(sqlite_integrity(ROOT / "data" / "sara_omega.db"))

    git_fsck = run(["git", "fsck", "--full", "--strict"])
    checks.append(
        {
            "name": "git_object_database",
            "pass": git_fsck["returncode"] == 0,
            "result": git_fsck,
        }
    )

    checks.append(docker_build())

    custom_gpt_resolver = run(
        [
            python,
            "tools/custom_gpt_action_sync_resolver.py",
        ],
        timeout=180,
    )
    checks.append(
        {
            "name": "custom_gpt_action_sync_resolver",
            "pass": custom_gpt_resolver["returncode"] == 0,
            "result": custom_gpt_resolver,
        }
    )

    required_pass = all(
        check["pass"]
        for check in checks
        if check["name"] != "docker_build"
    )
    docker_ready = next(check for check in checks if check["name"] == "docker_build")["pass"]

    report = {
        "project": "SARA-OMEGA V3.2.1",
        "root": str(ROOT),
        "required_local_gates_passed": required_pass,
        "docker_build_passed": docker_ready,
        "custom_gpt_editor_sync": {
            "status": "resolver_ready" if required_pass else "blocked",
            "reason": (
                "Hosted schema and gateway contract are resolver-verified; final editor import remains a ChatGPT UI action."
                if required_pass
                else "One or more local acceptance or Custom GPT sync resolver gates failed."
            ),
            "schema_url": "https://sara-omega-production.up.railway.app/gpt/action/openapi.yaml",
        },
        "checks": checks,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if required_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
