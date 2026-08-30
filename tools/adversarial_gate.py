from __future__ import annotations

import asyncio
import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from sara_v32_hardening import (
    AuthorityLevel,
    BackupIntegrityError,
    EpistemicDenied,
    EpistemicEnvelope,
    EpistemicStatus,
    FailSafeEvent,
    FailSafeSaveController,
    SIOSProtocolError,
    SIOSRelay,
)


async def main() -> int:
    checks = []

    def ok(name):
        checks.append((name, True, ""))

    def fail(name, exc):
        checks.append((name, False, str(exc)))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "backups"
        ctl = FailSafeSaveController(root, lambda: b"A" * 64)
        try:
            r1 = ctl.checkpoint({"state": "safe", "token": "secret"}, FailSafeEvent.PRE_MUTATION)
            if ctl.restore_latest().state["token"] != "[REDACTED]":
                raise AssertionError("secret not scrubbed")
            ok("backup_secret_scrub")
        except Exception as exc:
            fail("backup_secret_scrub", exc)

        try:
            p = Path(r1.path)
            doc = json.loads(p.read_text())
            doc["event"] = "SHUTDOWN"
            p.write_text(json.dumps(doc))
            try:
                ctl.verify(p)
            except BackupIntegrityError:
                ok("backup_tamper_detect")
            else:
                raise AssertionError("tampered backup accepted")
        except Exception as exc:
            fail("backup_tamper_detect", exc)

        try:
            ctl.checkpoint({"state": "known-good"}, FailSafeEvent.MANUAL)
            newest = ctl.checkpoint({"state": "newer"}, FailSafeEvent.MANUAL)
            Path(newest.path).write_text("{broken")
            restored = ctl.restore_latest()
            if not restored.fallback_used or restored.state["state"] != "known-good":
                raise AssertionError("fallback failed")
            ok("backup_corruption_fallback")
        except Exception as exc:
            fail("backup_corruption_fallback", exc)

    calls = 0

    async def token():
        return "trusted"

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    relay = SIOSRelay("https://sios.example", token, client=client)
    inferred = EpistemicEnvelope("guess", EpistemicStatus.INFERRED, .9, ["src:1"])
    try:
        try:
            await relay.dispatch("/v1/execute", {}, epistemic=inferred, authority=AuthorityLevel.EXECUTION)
        except EpistemicDenied:
            if calls != 0:
                raise AssertionError("network called before epistemic denial")
            ok("epistemic_pre_network_deny")
        else:
            raise AssertionError("inferred claim received execution authority")
    except Exception as exc:
        fail("epistemic_pre_network_deny", exc)

    verified = EpistemicEnvelope("verified", EpistemicStatus.VERIFIED, 1.0, ["src:1"], "receipt:1")
    try:
        try:
            await relay.dispatch("/../escape", {}, epistemic=verified, authority=AuthorityLevel.EXECUTION)
        except SIOSProtocolError:
            ok("relay_path_traversal_block")
        else:
            raise AssertionError("path traversal accepted")
    except Exception as exc:
        fail("relay_path_traversal_block", exc)
    await client.aclose()

    passed = sum(1 for _, good, _ in checks if good)
    print(json.dumps({"passed": passed, "total": len(checks), "checks": [{"name": n, "pass": g, "detail": d} for n, g, d in checks]}, indent=2))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
