from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _tool_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["SARA_DATA_DIR"] = str(tmp_path)
    env["SARA_MEMORY_KEY_HEX"] = "61" * 32
    env["SARA_ENROLLMENT_ID"] = "SARA-NEW-USER"
    env["SARA_PUBLIC_BASE_URL"] = "https://sara.example"
    return env


def test_first_user_invite_tool_creates_one_durable_invitation_and_is_idempotent(tmp_path: Path):
    env = _tool_env(tmp_path)
    tool = Path("tools/create_first_user_invite_once.py")

    first_run = subprocess.run(
        [sys.executable, str(tool)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first_run.returncode == 0, first_run.stderr

    outbox = tmp_path / "sara_first_user_invite.json"
    assert outbox.exists()
    first = json.loads(outbox.read_text(encoding="utf-8"))
    assert first["enrollment_id"] == "SARA-NEW-USER"
    assert first["enrollment_url"].startswith("https://sara.example/enroll/")
    assert first["expires_at"]
    assert first["enrollment_url"] not in first_run.stdout

    with sqlite3.connect(tmp_path / "sara_identity.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM enrollment_invites").fetchone()[0] == 1

    second_run = subprocess.run(
        [sys.executable, str(tool)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert second_run.returncode == 0, second_run.stderr
    second = json.loads(outbox.read_text(encoding="utf-8"))
    assert second == first

    with sqlite3.connect(tmp_path / "sara_identity.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM enrollment_invites").fetchone()[0] == 1

    if os.name != "nt":
        assert outbox.stat().st_mode & 0o777 == 0o600
