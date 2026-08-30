"""SARA OMEGA SIOS V3.2 hardening controls.

Includes epistemic authority gating, hardened SIOS relay, encrypted fail-safe
checkpoint/restore control, and runtime integration helpers.
"""
from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Stable UTF-8 JSON representation used for hashes, MACs, and receipts."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Sequence


class EpistemicStatus(str, Enum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"


class AuthorityLevel(str, Enum):
    OBSERVATIONAL = "OBSERVATIONAL"
    ADVISORY = "ADVISORY"
    EXECUTION = "EXECUTION"


class EpistemicDenied(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class EpistemicEnvelope:
    claim: str
    status: EpistemicStatus
    confidence: float
    evidence_refs: Sequence[str] = field(default_factory=tuple)
    verifier_receipt: str | None = None
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError("claim must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if any(not str(ref).strip() for ref in self.evidence_refs):
            raise ValueError("evidence refs must be non-empty")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["status"] = self.status.value
        value["evidence_refs"] = list(self.evidence_refs)
        return value


@dataclass(frozen=True, slots=True)
class EpistemicDecision:
    allowed: bool
    authority: AuthorityLevel
    reason: str


class EpistemicPolicy:
    """
    Non-bypassable truth/authority boundary.

    EXECUTION requires VERIFIED evidence plus a verifier receipt.
    SUPPORTED information may advise, but cannot independently authorize execution.
    INFERRED/UNCERTAIN/UNVERIFIED are observational only.
    CONTRADICTED is denied at every authority level.
    """

    def evaluate(
        self,
        envelope: EpistemicEnvelope,
        authority: AuthorityLevel,
    ) -> EpistemicDecision:
        if envelope.status is EpistemicStatus.CONTRADICTED:
            return EpistemicDecision(False, authority, "contradicted_claim")

        if authority is AuthorityLevel.OBSERVATIONAL:
            return EpistemicDecision(True, authority, "observation_only")

        if authority is AuthorityLevel.ADVISORY:
            if envelope.status not in {EpistemicStatus.SUPPORTED, EpistemicStatus.VERIFIED}:
                return EpistemicDecision(False, authority, "insufficient_epistemic_status_for_advice")
            if not envelope.evidence_refs:
                return EpistemicDecision(False, authority, "advice_requires_evidence")
            return EpistemicDecision(True, authority, "advisory_evidence_satisfied")

        if authority is AuthorityLevel.EXECUTION:
            if envelope.status is not EpistemicStatus.VERIFIED:
                return EpistemicDecision(False, authority, "execution_requires_verified_status")
            if not envelope.evidence_refs:
                return EpistemicDecision(False, authority, "execution_requires_evidence")
            if not (envelope.verifier_receipt or "").strip():
                return EpistemicDecision(False, authority, "execution_requires_verifier_receipt")
            return EpistemicDecision(True, authority, "execution_epistemic_gate_passed")

        return EpistemicDecision(False, authority, "unknown_authority")

    def require(self, envelope: EpistemicEnvelope, authority: AuthorityLevel) -> None:
        decision = self.evaluate(envelope, authority)
        if not decision.allowed:
            raise EpistemicDenied(decision.reason)


import base64
import hashlib
import hmac
import os
import re
import secrets
import tempfile
import threading
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


MasterKeyProvider = Callable[[], bytes]


class BackupError(RuntimeError):
    pass


class BackupIntegrityError(BackupError):
    pass


class BackupConfigurationError(BackupError):
    pass


class FailSafeEvent(str, Enum):
    PRE_MUTATION = "PRE_MUTATION"
    PRE_DISPATCH = "PRE_DISPATCH"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    SECURITY_CONTAINMENT = "SECURITY_CONTAINMENT"
    UNHANDLED_EXCEPTION = "UNHANDLED_EXCEPTION"
    SHUTDOWN = "SHUTDOWN"
    MANUAL = "MANUAL"


@dataclass(frozen=True, slots=True)
class SnapshotReceipt:
    snapshot_id: str
    path: str
    event: FailSafeEvent
    created_at: str
    state_sha3_512: str
    chain_digest: str
    previous_chain_digest: str | None


@dataclass(frozen=True, slots=True)
class RestoreResult:
    snapshot_id: str
    state: dict[str, Any]
    receipt: SnapshotReceipt
    fallback_used: bool


_SENSITIVE = {
    "password", "passwd", "token", "access_token", "refresh_token",
    "authorization", "cookie", "secret", "api_key", "apikey",
    "private_key", "client_secret",
}
_SAFE_REFERENCE_SUFFIXES = ("_ref", "_reference", "_id", "_name", "_arn", "_uri")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: str, max_chars: int = 512) -> str:
    return _CONTROL_CHARS.sub("?", value.replace("\r", "\\r").replace("\n", "\\n"))[:max_chars]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized.endswith(_SAFE_REFERENCE_SUFFIXES):
        return False
    if normalized in _SENSITIVE:
        return True
    return any(normalized.endswith("_" + item) or normalized.startswith(item + "_") for item in _SENSITIVE)


def sanitize_for_backup(value: Any, *, depth: int = 0) -> Any:
    if depth > 20:
        raise BackupError("backup state exceeds maximum nesting depth")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value, max_chars=100_000)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            name = _safe_text(str(key), max_chars=256)
            result[name] = "[REDACTED]" if _is_sensitive_key(name) else sanitize_for_backup(child, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize_for_backup(item, depth=depth + 1) for item in value]
    raise BackupError(f"unsupported backup value type: {type(value).__name__}")


class FailSafeSaveController:
    """Encrypted, atomic, tamper-evident SARA state checkpoints."""

    FORMAT_VERSION = 1
    AAD = b"SARA-OMEGA-SIOS-V3.2-FAILSAFE-SNAPSHOT-V1"

    def __init__(self, root: str | Path, master_key_provider: MasterKeyProvider, *, max_snapshot_bytes: int = 8 * 1024 * 1024, max_snapshots: int = 50) -> None:
        self.root = Path(root).expanduser().resolve()
        self.master_key_provider = master_key_provider
        self.max_snapshot_bytes = max_snapshot_bytes
        self.max_snapshots = max_snapshots
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        if self.max_snapshot_bytes < 1024:
            raise ValueError("max_snapshot_bytes is too small")
        if self.max_snapshots < 2:
            raise ValueError("max_snapshots must be >= 2")

    def _master_key(self) -> bytes:
        key = self.master_key_provider()
        if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
            raise BackupConfigurationError("master key must be at least 32 bytes")
        return bytes(key)

    def _derive_keys(self) -> tuple[bytes, bytes]:
        material = HKDF(algorithm=hashes.SHA3_512(), length=64, salt=b"SARA-OMEGA-SIOS-V3.2", info=b"failsafe-backup-controller").derive(self._master_key())
        return material[:32], material[32:]

    def _snapshot_files(self) -> list[Path]:
        return sorted(self.root.glob("snapshot-*.json"), key=lambda p: p.name, reverse=True)

    def _latest_valid_digest(self) -> str | None:
        for path in self._snapshot_files():
            try:
                envelope = self._load_and_verify_envelope(path)
                return str(envelope["chain_digest"])
            except BackupError:
                continue
        return None

    def checkpoint(self, state: Mapping[str, Any], event: FailSafeEvent, *, correlation_id: str = "", metadata: Mapping[str, Any] | None = None) -> SnapshotReceipt:
        with self._lock:
            clean_state = sanitize_for_backup(dict(state))
            clean_metadata = sanitize_for_backup(dict(metadata or {}))
            payload = canonical_json_bytes(clean_state)
            if len(payload) > self.max_snapshot_bytes:
                raise BackupError("snapshot exceeds configured size limit")
            state_digest = hashlib.sha3_512(payload).hexdigest()
            previous_digest = self._latest_valid_digest()
            enc_key, mac_key = self._derive_keys()
            nonce = secrets.token_bytes(12)
            ciphertext = AESGCM(enc_key).encrypt(nonce, payload, self.AAD)
            created_at = _utc_now()
            snapshot_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{secrets.token_hex(6)}"
            envelope: dict[str, Any] = {
                "format_version": self.FORMAT_VERSION,
                "snapshot_id": snapshot_id,
                "created_at": created_at,
                "event": event.value,
                "correlation_id": _safe_text(correlation_id, 256),
                "metadata": clean_metadata,
                "cipher": "AES-256-GCM",
                "kdf": "HKDF-SHA3-512",
                "nonce_b64": base64.b64encode(nonce).decode("ascii"),
                "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
                "state_sha3_512": state_digest,
                "previous_chain_digest": previous_digest,
            }
            chain_digest = hashlib.sha3_512(canonical_json_bytes(envelope)).hexdigest()
            envelope["chain_digest"] = chain_digest
            envelope["mac_sha3_512"] = hmac.new(mac_key, canonical_json_bytes(envelope), hashlib.sha3_512).hexdigest()
            final_bytes = canonical_json_bytes(envelope) + b"\n"
            path = self.root / f"snapshot-{snapshot_id}.json"
            self._atomic_write(path, final_bytes)
            self._atomic_write(self.root / "latest.json", canonical_json_bytes({"snapshot_id": snapshot_id, "file": path.name, "chain_digest": chain_digest}) + b"\n")
            self._enforce_retention()
            return SnapshotReceipt(snapshot_id, str(path), event, created_at, state_digest, chain_digest, previous_digest)

    def _atomic_write(self, path: Path, data: bytes) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp-sara-", dir=str(self.root))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            dir_fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _enforce_retention(self) -> None:
        for old in self._snapshot_files()[self.max_snapshots:]:
            try:
                old.unlink()
            except FileNotFoundError:
                pass

    def _load_and_verify_envelope(self, path: Path) -> dict[str, Any]:
        try:
            envelope = json.loads(path.read_bytes())
        except Exception as exc:
            raise BackupIntegrityError(f"snapshot parse failed: {path.name}") from exc
        required = {"format_version", "snapshot_id", "created_at", "event", "nonce_b64", "ciphertext_b64", "state_sha3_512", "chain_digest", "mac_sha3_512"}
        if not required.issubset(envelope):
            raise BackupIntegrityError("snapshot missing required fields")
        if envelope["format_version"] != self.FORMAT_VERSION:
            raise BackupIntegrityError("unsupported snapshot format")
        _enc_key, mac_key = self._derive_keys()
        supplied_mac = str(envelope["mac_sha3_512"])
        without_mac = dict(envelope)
        without_mac.pop("mac_sha3_512", None)
        expected_mac = hmac.new(mac_key, canonical_json_bytes(without_mac), hashlib.sha3_512).hexdigest()
        if not hmac.compare_digest(supplied_mac, expected_mac):
            raise BackupIntegrityError("snapshot MAC verification failed")
        supplied_chain = str(envelope["chain_digest"])
        without_chain = dict(without_mac)
        without_chain.pop("chain_digest", None)
        expected_chain = hashlib.sha3_512(canonical_json_bytes(without_chain)).hexdigest()
        if not hmac.compare_digest(supplied_chain, expected_chain):
            raise BackupIntegrityError("snapshot chain digest verification failed")
        return envelope

    def _decrypt_state(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        enc_key, _mac_key = self._derive_keys()
        try:
            nonce = base64.b64decode(str(envelope["nonce_b64"]), validate=True)
            ciphertext = base64.b64decode(str(envelope["ciphertext_b64"]), validate=True)
            plaintext = AESGCM(enc_key).decrypt(nonce, ciphertext, self.AAD)
            state = json.loads(plaintext)
        except Exception as exc:
            raise BackupIntegrityError("snapshot decryption/authentication failed") from exc
        if not isinstance(state, dict):
            raise BackupIntegrityError("snapshot root state is not an object")
        return state

    def _receipt(self, path: Path, envelope: Mapping[str, Any]) -> SnapshotReceipt:
        try:
            event = FailSafeEvent(str(envelope["event"]))
        except ValueError as exc:
            raise BackupIntegrityError("unknown fail-safe event") from exc
        return SnapshotReceipt(str(envelope["snapshot_id"]), str(path), event, str(envelope["created_at"]), str(envelope["state_sha3_512"]), str(envelope["chain_digest"]), str(envelope["previous_chain_digest"]) if envelope.get("previous_chain_digest") else None)

    def verify(self, path: str | Path) -> SnapshotReceipt:
        with self._lock:
            candidate = Path(path).expanduser().resolve()
            if candidate.parent != self.root:
                raise BackupIntegrityError("snapshot path is outside backup root")
            envelope = self._load_and_verify_envelope(candidate)
            state = self._decrypt_state(envelope)
            digest = hashlib.sha3_512(canonical_json_bytes(state)).hexdigest()
            if not hmac.compare_digest(digest, str(envelope["state_sha3_512"])):
                raise BackupIntegrityError("restored state digest mismatch")
            return self._receipt(candidate, envelope)

    def restore_latest(self) -> RestoreResult:
        with self._lock:
            files = self._snapshot_files()
            if not files:
                raise BackupError("no snapshots available")
            newest_name = files[0].name
            for path in files:
                try:
                    envelope = self._load_and_verify_envelope(path)
                    state = self._decrypt_state(envelope)
                    digest = hashlib.sha3_512(canonical_json_bytes(state)).hexdigest()
                    if not hmac.compare_digest(digest, str(envelope["state_sha3_512"])):
                        raise BackupIntegrityError("restored state digest mismatch")
                    return RestoreResult(str(envelope["snapshot_id"]), state, self._receipt(path, envelope), path.name != newest_name)
                except BackupError:
                    continue
            raise BackupIntegrityError("no valid snapshot remains")

    def verify_retained_chain(self) -> bool:
        with self._lock:
            files = list(reversed(self._snapshot_files()))
            prior_digest: str | None = None
            for index, path in enumerate(files):
                envelope = self._load_and_verify_envelope(path)
                declared_prev = envelope.get("previous_chain_digest")
                if index > 0 and declared_prev != prior_digest:
                    raise BackupIntegrityError("retained snapshot chain discontinuity")
                prior_digest = str(envelope["chain_digest"])
            return True


class SIOSRelayError(RuntimeError):
    pass


class SIOSUnavailable(SIOSRelayError):
    pass


class SIOSRejected(SIOSRelayError):
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"SIOS rejected request: HTTP {status_code}")


class SIOSProtocolError(SIOSRelayError):
    pass


TokenProvider = Callable[[], Awaitable[str]]


class SIOSRelay:
    """Internal SARA -> SIOS relay with bounded, fail-closed behavior."""

    def __init__(self, base_url: str, token_provider: TokenProvider, *, client: httpx.AsyncClient | None = None, epistemic_policy: EpistemicPolicy | None = None, max_response_bytes: int = 2 * 1024 * 1024, allow_insecure_localhost: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_provider = token_provider
        self.epistemic_policy = epistemic_policy or EpistemicPolicy()
        self.max_response_bytes = max_response_bytes
        self._owns_client = client is None
        self._validate_base_url(allow_insecure_localhost)
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=3.0), limits=httpx.Limits(max_connections=20, max_keepalive_connections=10), follow_redirects=False)

    def _validate_base_url(self, allow_insecure_localhost: bool) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme == "https" and parsed.netloc:
            return
        if allow_insecure_localhost and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            return
        raise ValueError("SIOS base URL must use HTTPS")

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def dispatch(self, path: str, payload: Mapping[str, Any], *, epistemic: EpistemicEnvelope, authority: AuthorityLevel, correlation_id: str | None = None) -> Any:
        self.epistemic_policy.require(epistemic, authority)
        if not path.startswith("/") or path.startswith("//") or ".." in path.split("/"):
            raise SIOSProtocolError("invalid SIOS path")
        if self.max_response_bytes < 1024:
            raise SIOSProtocolError("max_response_bytes too small")
        token = await self.token_provider()
        if not token or not token.strip():
            raise SIOSUnavailable("SIOS token provider returned no token")
        request_id = correlation_id or str(__import__('uuid').uuid4())
        nonce = secrets.token_urlsafe(32)
        headers = {
            "Authorization": f"Bearer {token.strip()}",
            "X-SARA-Nonce": nonce,
            "X-SARA-Timestamp": str(int(__import__('time').time())),
            "X-SARA-Request-Id": request_id,
            "X-SARA-Idempotency-Key": secrets.token_urlsafe(24),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        outbound = {"payload": dict(payload), "epistemic": epistemic.to_dict(), "authority": authority.value}
        url = f"{self.base_url}{path}"
        try:
            async with self.client.stream("POST", url, json=outbound, headers=headers) as response:
                if 300 <= response.status_code < 400:
                    raise SIOSProtocolError("SIOS redirects are forbidden")
                if response.status_code >= 500:
                    raise SIOSUnavailable(f"SIOS unavailable: HTTP {response.status_code}")
                body = await self._bounded_json(response)
                if response.status_code >= 400:
                    raise SIOSRejected(response.status_code, body)
                return body
        except SIOSRelayError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SIOSUnavailable("SIOS transport unavailable") from exc

    async def _bounded_json(self, response: httpx.Response) -> Any:
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_response_bytes:
                    raise SIOSProtocolError("SIOS response exceeds configured size limit")
            except ValueError as exc:
                raise SIOSProtocolError("invalid Content-Length from SIOS") from exc
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise SIOSProtocolError("SIOS response must be application/json")
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > self.max_response_bytes:
                raise SIOSProtocolError("SIOS response exceeds configured size limit")
        try:
            return json.loads(bytes(data))
        except ValueError as exc:
            raise SIOSProtocolError("SIOS returned invalid JSON") from exc


class V32FailSafeBridge:
    """Thin integration boundary for V3.2 trusted mutation and SIOS dispatch paths."""

    def __init__(self, saves: FailSafeSaveController, relay: SIOSRelay) -> None:
        self.saves = saves
        self.relay = relay

    def before_mutation(self, current_state: Mapping[str, Any], *, correlation_id: str, metadata: Mapping[str, Any] | None = None) -> SnapshotReceipt:
        return self.saves.checkpoint(current_state, FailSafeEvent.PRE_MUTATION, correlation_id=correlation_id, metadata=metadata)

    async def dispatch_with_checkpoint(self, current_state: Mapping[str, Any], path: str, payload: Mapping[str, Any], *, epistemic: EpistemicEnvelope, authority: AuthorityLevel, correlation_id: str) -> Any:
        self.saves.checkpoint(current_state, FailSafeEvent.PRE_DISPATCH, correlation_id=correlation_id, metadata={"path": path, "authority": authority.value})
        try:
            return await self.relay.dispatch(path, payload, epistemic=epistemic, authority=authority, correlation_id=correlation_id)
        except SIOSRelayError:
            self.saves.checkpoint(current_state, FailSafeEvent.PROVIDER_UNAVAILABLE, correlation_id=correlation_id, metadata={"path": path, "authority": authority.value})
            raise


class RuntimeFailSafe:
    """Environment-bound runtime wrapper for the fail-safe controller."""

    def __init__(self, controller: FailSafeSaveController | None, *, required: bool, root: str, init_error: str = "") -> None:
        self.controller = controller
        self.required = required
        self.root = root
        self.init_error = init_error

    @classmethod
    def from_env(cls) -> "RuntimeFailSafe":
        required = os.environ.get("SARA_FAILSAFE_REQUIRED", "false").strip().lower() == "true"
        root = os.environ.get("SARA_FAILSAFE_ROOT", "/tmp/sara-failsafe").strip() or "/tmp/sara-failsafe"
        raw_hex = os.environ.get("SARA_FAILSAFE_MASTER_KEY_HEX", "").strip()
        raw_b64 = os.environ.get("SARA_FAILSAFE_MASTER_KEY_B64", "").strip()
        if not raw_hex and not raw_b64:
            return cls(None, required=required, root=root, init_error="failsafe_master_key_not_configured")
        try:
            key = bytes.fromhex(raw_hex) if raw_hex else base64.b64decode(raw_b64, validate=True)
            if len(key) < 32:
                raise ValueError("master key must be at least 32 bytes")
            controller = FailSafeSaveController(Path(root), lambda: key, max_snapshot_bytes=int(os.environ.get("SARA_FAILSAFE_MAX_SNAPSHOT_BYTES", str(8 * 1024 * 1024))), max_snapshots=int(os.environ.get("SARA_FAILSAFE_MAX_SNAPSHOTS", "50")))
            return cls(controller, required=required, root=root)
        except Exception as exc:
            return cls(None, required=required, root=root, init_error=f"failsafe_init_failed:{type(exc).__name__}")

    @property
    def configured(self) -> bool:
        return self.controller is not None

    def status(self) -> dict[str, Any]:
        return {"configured": self.configured, "required": self.required, "root": self.root, "init_error": self.init_error or None}

    def ensure_ready(self) -> None:
        if self.required and self.controller is None:
            raise BackupConfigurationError(self.init_error or "failsafe_not_configured")

    def checkpoint(self, state: Mapping[str, Any], event: FailSafeEvent, *, correlation_id: str = "", metadata: Mapping[str, Any] | None = None) -> SnapshotReceipt | None:
        if self.controller is None:
            self.ensure_ready()
            return None
        return self.controller.checkpoint(state, event, correlation_id=correlation_id, metadata=metadata)

    def restore_latest(self) -> RestoreResult:
        self.ensure_ready()
        if self.controller is None:
            raise BackupConfigurationError(self.init_error or "failsafe_not_configured")
        return self.controller.restore_latest()

    def verify_retained_chain(self) -> bool:
        self.ensure_ready()
        if self.controller is None:
            raise BackupConfigurationError(self.init_error or "failsafe_not_configured")
        return self.controller.verify_retained_chain()
