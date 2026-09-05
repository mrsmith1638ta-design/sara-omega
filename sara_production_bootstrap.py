"""SARA-OMEGA V.3.2 production bootstrap and Railway acceptance controller.

This module runs before Uvicorn. It makes the V3.2 fail-safe controls production-
enforcing without making the public liveness endpoint disappear when configuration
is incomplete: an incomplete/unsafe configuration leaves the process diagnosable
but forces SARA's existing readiness and state-mutation gates to fail closed.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Request

from sara_v32_hardening import BackupError, FailSafeEvent, RuntimeFailSafe

PROJECT_NAME = "SARA-OMEGA V.3.2.1"
RELEASE_VERSION = "3.2.1"
HARDENING_PROFILE = "SIOS-V3.2-FAILSAFE-1"
DEFAULT_FAILSAFE_ROOT = "/data/sara-failsafe"
MARKER_NAME = "runtime-persistence-marker.json"
EVIDENCE_NAME = "production-acceptance.json"
SOURCE_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")

logger = logging.getLogger("sara.production_bootstrap")


class ProductionPreflightError(RuntimeError):
    """Raised when a required production trust predicate is not satisfied."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _source_commit_sha() -> str | None:
    raw = os.environ.get("SARA_SOURCE_COMMIT_SHA", "").strip()
    if not SOURCE_COMMIT_RE.fullmatch(raw):
        return None
    return raw.lower()


def configure_production_defaults() -> None:
    """Set secure defaults without overwriting explicit operator configuration."""
    os.environ.setdefault("SARA_FAILSAFE_REQUIRED", "true")
    os.environ.setdefault("SARA_FAILSAFE_ROOT", DEFAULT_FAILSAFE_ROOT)
    os.environ.setdefault("SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT", "true")
    os.environ.setdefault("SARA_FAILSAFE_MIN_FREE_BYTES", str(64 * 1024 * 1024))


def nearest_mount_point(path: str | Path) -> Path:
    """Return the closest mounted ancestor for a path."""
    candidate = Path(path).expanduser().resolve()
    existing = candidate
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    while existing != existing.parent and not os.path.ismount(existing):
        existing = existing.parent
    return existing


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-sara-acceptance-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", closefd=True) as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_marker(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(value, dict):
        return None
    if value.get("project_name") != PROJECT_NAME:
        return None
    if not isinstance(value.get("boot_id"), str) or not value["boot_id"]:
        return None
    return value


def _writable_probe(root: Path) -> None:
    fd, name = tempfile.mkstemp(prefix=".sara-write-probe-", dir=str(root))
    try:
        os.write(fd, b"SARA-OMEGA-V3.2")
        os.fsync(fd)
    finally:
        os.close(fd)
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def run_preflight() -> dict[str, Any]:
    """Execute evidence-based production checks and return non-secret evidence."""
    configure_production_defaults()

    insecure_override = _env_bool("SARA_PRODUCTION_ALLOW_INSECURE_OVERRIDE", False)
    required = _env_bool("SARA_FAILSAFE_REQUIRED", True)
    if not required and not insecure_override:
        raise ProductionPreflightError("failsafe_required_must_be_true")

    owner_token_configured = bool(os.environ.get("OWNER_TOKEN", "").strip())
    if not owner_token_configured and not insecure_override:
        raise ProductionPreflightError("owner_token_not_configured")
    source_commit_sha = _source_commit_sha()

    runtime = RuntimeFailSafe.from_env()
    try:
        runtime.ensure_ready()
    except BackupError as exc:
        raise ProductionPreflightError(f"failsafe_not_ready:{type(exc).__name__}") from exc
    if runtime.controller is None:
        raise ProductionPreflightError("failsafe_controller_not_configured")

    root = Path(runtime.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _writable_probe(root)

    mount_point = nearest_mount_point(root)
    dedicated_mount_required = _env_bool("SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT", True)
    root_on_dedicated_mount = mount_point != Path("/")
    if dedicated_mount_required and not root_on_dedicated_mount and not insecure_override:
        raise ProductionPreflightError("failsafe_root_not_on_dedicated_mount")

    min_free_bytes = int(os.environ.get("SARA_FAILSAFE_MIN_FREE_BYTES", str(64 * 1024 * 1024)))
    free_bytes = shutil.disk_usage(root).free
    if free_bytes < min_free_bytes and not insecure_override:
        raise ProductionPreflightError("failsafe_volume_low_space")

    marker_path = root / MARKER_NAME
    previous_marker = _read_marker(marker_path)
    boot_id = str(uuid.uuid4())

    receipt = runtime.checkpoint(
        {
            "project_name": PROJECT_NAME,
            "release_version": RELEASE_VERSION,
            "hardening_profile": HARDENING_PROFILE,
            "bootstrap_probe": True,
            "boot_id": boot_id,
        },
        FailSafeEvent.MANUAL,
        correlation_id=f"bootstrap-{boot_id}",
        metadata={"purpose": "production_bootstrap_self_test"},
    )
    if receipt is None:
        raise ProductionPreflightError("bootstrap_checkpoint_not_created")

    verified_receipt = runtime.controller.verify(receipt.path)
    if verified_receipt.snapshot_id != receipt.snapshot_id:
        raise ProductionPreflightError("bootstrap_snapshot_verification_mismatch")
    chain_valid = runtime.verify_retained_chain()
    if not chain_valid:
        raise ProductionPreflightError("bootstrap_chain_invalid")

    persistence_observed = bool(previous_marker and previous_marker.get("boot_id") != boot_id)
    marker = {
        "project_name": PROJECT_NAME,
        "release_version": RELEASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "boot_id": boot_id,
        "created_at_epoch": int(time.time()),
        "bootstrap_snapshot_id": receipt.snapshot_id,
        "chain_digest": receipt.chain_digest,
    }
    _atomic_json(marker_path, marker)

    evidence: dict[str, Any] = {
        "project_name": PROJECT_NAME,
        "release_version": RELEASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "bootstrap_ready": True,
        "failsafe_required": required,
        "failsafe_configured": runtime.configured,
        "owner_token_configured": owner_token_configured,
        "dedicated_mount_required": dedicated_mount_required,
        "root_on_dedicated_mount": root_on_dedicated_mount,
        "mount_point": str(mount_point),
        "free_bytes": free_bytes,
        "min_free_bytes": min_free_bytes,
        "checkpoint_self_test": True,
        "checkpoint_snapshot_id": receipt.snapshot_id,
        "chain_valid": True,
        "persistence_observed_across_boots": persistence_observed,
        "persistence_status": "PROVEN" if persistence_observed else "PENDING_RESTART_PROOF",
        "production_accepted": bool(
            required
            and runtime.configured
            and owner_token_configured
            and (root_on_dedicated_mount or not dedicated_mount_required or insecure_override)
            and chain_valid
            and persistence_observed
        ),
    }
    if source_commit_sha:
        evidence["source_commit_sha"] = source_commit_sha
    _atomic_json(root / EVIDENCE_NAME, evidence)
    return evidence


def failed_evidence(exc: BaseException) -> dict[str, Any]:
    return {
        "project_name": PROJECT_NAME,
        "release_version": RELEASE_VERSION,
        "hardening_profile": HARDENING_PROFILE,
        "bootstrap_ready": False,
        "production_accepted": False,
        "persistence_observed_across_boots": False,
        "persistence_status": "UNPROVEN",
        "failure": type(exc).__name__,
        "failure_reason": str(exc)[:256],
    }


def register_acceptance_routes(main_module: Any, evidence: dict[str, Any]) -> None:
    """Attach sanitized public and owner-only live acceptance endpoints."""
    app = main_module.app

    @app.get("/health/production-acceptance")
    def production_acceptance_health():
        public_keys = {
            "project_name",
            "release_version",
            "hardening_profile",
            "source_commit_sha",
            "bootstrap_ready",
            "production_accepted",
            "failsafe_required",
            "failsafe_configured",
            "owner_token_configured",
            "dedicated_mount_required",
            "root_on_dedicated_mount",
            "checkpoint_self_test",
            "chain_valid",
            "persistence_observed_across_boots",
            "persistence_status",
            "failure",
            "failure_reason",
        }
        return {key: evidence.get(key) for key in public_keys if key in evidence}

    @app.get("/admin/production-acceptance")
    def production_acceptance_admin(req: Request):
        if main_module.authorize(req) != "owner":
            raise main_module.HTTPException(403, "Owner only")
        live = dict(evidence)
        live["failsafe_runtime"] = main_module.FAILSAFE.status()
        if main_module.FAILSAFE.configured:
            try:
                live["chain_valid_now"] = main_module.FAILSAFE.verify_retained_chain()
            except BackupError:
                live["chain_valid_now"] = False
        else:
            live["chain_valid_now"] = False
        live["production_accepted_now"] = bool(
            live.get("production_accepted") and live.get("chain_valid_now")
        )
        return live


def run() -> None:
    if _env_bool("SARA_NO_START", False):
        logger.warning("SARA production bootstrap NO-START: cost-control gate active")
        raise SystemExit(0)
    configure_production_defaults()
    try:
        evidence = run_preflight()
        logger.info("SARA production bootstrap PASS: %s", evidence.get("persistence_status"))
    except Exception as exc:
        evidence = failed_evidence(exc)
        logger.error("SARA production bootstrap BLOCKED: %s", evidence.get("failure_reason"))

    # Import only after secure defaults are established so main.FAILSAFE binds to them.
    import main as main_module

    if not evidence.get("bootstrap_ready"):
        # Keep liveness/diagnostics available, but make all protected mutations and
        # /health/ready fail closed through the existing RuntimeFailSafe boundary.
        main_module.FAILSAFE.required = True
        main_module.FAILSAFE.controller = None
        main_module.FAILSAFE.init_error = "production_bootstrap_gate_failed"

    register_acceptance_routes(main_module, evidence)
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(main_module.app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
