#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OAUTH_BASE = "https://backboard.railway.com/oauth"
CLIENT_ID = "rlwy_oaci_onEklvmksh1hRUiCo7E2zX12"
SCOPES = "openid email profile offline_access workspace:admin project:admin ssh_keys"
GITHUB_API = "https://api.github.com"


def post_form(url: str, data: dict[str, str]) -> tuple[int, str]:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "sara-omega-v3.2.1-railway-oauth",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def github_issue(title: str, body: str) -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        raise RuntimeError("GitHub Actions identity unavailable")
    payload = json.dumps({"title": title, "body": body}).encode()
    req = urllib.request.Request(
        f"{GITHUB_API}/repos/{repo}/issues",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "sara-omega-v3.2.1-railway-oauth",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return int(data["number"])


def close_issue(number: int, status: str) -> None:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return
    payload = json.dumps({"state": "closed", "state_reason": "completed", "body": status}).encode()
    req = urllib.request.Request(
        f"{GITHUB_API}/repos/{repo}/issues/{number}",
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "sara-omega-v3.2.1-railway-oauth",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
    except Exception:
        pass


def write_cli_config(access_token: str, refresh_token: str | None, expires_in: int) -> None:
    root = Path.home() / ".railway"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / "config.json"
    user: dict[str, object] = {
        "accessToken": access_token,
        "tokenExpiresAt": int(time.time()) + expires_in,
    }
    if refresh_token:
        user["refreshToken"] = refresh_token
    config = {"projects": {}, "user": user}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, separators=(",", ":")), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def main() -> int:
    status, body = post_form(
        f"{OAUTH_BASE}/device/auth",
        {
            "client_id": CLIENT_ID,
            "scope": SCOPES,
            "cli_caller": "github_actions_sara_omega",
        },
    )
    if status // 100 != 2:
        print(f"Railway device authorization request failed: HTTP {status}", file=sys.stderr)
        return 2
    try:
        auth = json.loads(body)
        device_code = str(auth["device_code"])
        user_code = str(auth["user_code"])
        verify = str(auth["verification_uri"])
        verify_complete = str(auth.get("verification_uri_complete") or verify)
        expires_in = int(auth["expires_in"])
        interval = max(1, int(auth.get("interval", 5)))
    except Exception as exc:
        print(f"Railway device authorization response invalid: {type(exc).__name__}", file=sys.stderr)
        return 3

    run_id = os.environ.get("GITHUB_RUN_ID", "unknown")
    issue_body = (
        f"SARA-OMEGA V3.2.1 is waiting for Railway authorization for workflow run `{run_id}`.\n\n"
        f"**One-click authorization:** {verify_complete}\n\n"
        f"Fallback: open {verify} and enter code **`{user_code}`**.\n\n"
        "This is a short-lived OAuth device authorization. No API token, password, or secret should be pasted into GitHub or ChatGPT. "
        "After approval, this issue closes automatically and deployment continues."
    )
    issue = github_issue(
        f"Railway OAuth approval required — SARA-OMEGA V3.2.1 run {run_id}",
        issue_body,
    )
    Path("railway-oauth-issue.txt").write_text(str(issue) + "\n", encoding="utf-8")
    print(f"Railway authorization issue created: #{issue}")
    print(f"Pairing code: {user_code}")
    print(f"Authorization URL: {verify_complete}")

    deadline = time.monotonic() + expires_in
    poll = interval
    while time.monotonic() < deadline:
        time.sleep(poll)
        status, token_body = post_form(
            f"{OAUTH_BASE}/token",
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": CLIENT_ID,
            },
        )
        if status // 100 == 2:
            try:
                token = json.loads(token_body)
                access_token = str(token["access_token"])
                refresh_token = token.get("refresh_token")
                token_expires = int(token["expires_in"])
            except Exception as exc:
                print(f"Railway token response invalid: {type(exc).__name__}", file=sys.stderr)
                close_issue(issue, "Railway authorization returned an invalid token response. Deployment stopped.")
                return 4
            write_cli_config(access_token, str(refresh_token) if refresh_token else None, token_expires)
            close_issue(issue, "Railway authorization completed successfully. SARA-OMEGA V3.2.1 deployment is continuing automatically.")
            print("Railway OAuth authorization completed; CLI session installed without exposing credentials.")
            return 0
        try:
            err = json.loads(token_body)
            code = str(err.get("error", "unknown_error"))
        except Exception:
            code = "unexpected_response"
        if code == "authorization_pending":
            continue
        if code == "slow_down":
            poll += 5
            continue
        if code in {"expired_token", "access_denied"}:
            close_issue(issue, f"Railway authorization ended with `{code}`. Deployment stopped safely.")
            print(f"Railway OAuth authorization ended: {code}", file=sys.stderr)
            return 5
        close_issue(issue, f"Railway authorization failed with `{code}`. Deployment stopped safely.")
        print(f"Railway OAuth token polling failed: {code}", file=sys.stderr)
        return 6

    close_issue(issue, "Railway authorization expired before completion. Deployment stopped safely.")
    print("Railway OAuth authorization expired", file=sys.stderr)
    return 7


if __name__ == "__main__":
    raise SystemExit(main())
