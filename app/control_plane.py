from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

BOUND_REPOSITORY = "mrsmith1638ta-design/sara-omega"
GITHUB_API_BASE = "https://api.github.com"
RAILWAY_API_BASE = "https://backboard.railway.com"
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SECRET_FIELD_RE = re.compile(r"(?:authorization|token|secret|credential|password|api[_-]?key|private[_-]?key)", re.I)
_ALLOWED_IDEMPOTENCY_STATES = {"RESERVED", "COMPLETED", "REJECTED", "SUBMISSION_UNVERIFIED"}

logger = logging.getLogger("sara.control_plane")


class PrivilegedControlError(RuntimeError):
    pass


class AuthenticationRejected(PrivilegedControlError):
    pass


class BindingRejected(PrivilegedControlError):
    pass


class CompareAndSwapRejected(PrivilegedControlError):
    pass


class IdempotencyConflict(PrivilegedControlError):
    pass


class SubmissionUnverified(PrivilegedControlError):
    pass


@dataclass(frozen=True)
class MutationRecord:
    bridge: str
    idempotency_key: str
    request_hash: str
    status: str
    result_json: str | None
    created_at: str
    updated_at: str

    @property
    def result(self) -> dict[str, Any] | None:
        return json.loads(self.result_json) if self.result_json else None


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_dir() -> Path:
    root = Path(os.getenv("SARA_DATA_DIR", "./data")).expanduser()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    return root


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise BindingRejected(f"missing_required_configuration:{name}")
    return value


def _validate_inbound_token(name: str, token: str, *, other_privileged: str = "") -> None:
    if not token:
        raise AuthenticationRejected(f"missing_privileged_authentication:{name}")
    forbidden = {
        os.getenv("OWNER_TOKEN", "").strip(),
        os.getenv("GPT_ACTION_TOKEN", "").strip(),
        os.getenv("TEST_TOKEN", "").strip(),
        other_privileged.strip(),
    }
    forbidden.discard("")
    if token in forbidden:
        raise AuthenticationRejected(f"privileged_token_not_separate:{name}")


def _authenticate(expected: str, supplied: str) -> None:
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise AuthenticationRejected("privileged_authentication_rejected")


def _validate_commit_sha(commit_sha: str) -> str:
    normalized = commit_sha.strip().lower()
    if not _COMMIT_RE.fullmatch(normalized):
        raise BindingRejected("exact_40_character_commit_sha_required")
    return normalized


def _request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _redact(value: Any, secrets: tuple[str, ...], *, key: str = "") -> Any:
    if key and _SECRET_FIELD_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, secrets, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item, secrets) for item in value[:50]]
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        redacted = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+\-/=]+", "[REDACTED]", redacted)
        return redacted[:512]
    return value


def sanitize_log_record(
    event: str,
    fields: dict[str, Any] | None = None,
    *,
    secrets: Iterable[str] = (),
    max_chars: int = 1024,
) -> str:
    limit = max(128, min(int(max_chars), 4096))
    known = tuple(secret for secret in secrets if secret)
    payload = {
        "event": re.sub(r"[^A-Za-z0-9_.:-]", "_", event)[:128],
        "fields": _redact(fields or {}, known),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))[:limit]


class IdempotencyLedger:
    """Durable mutation reservation ledger. Reservation commits before external writes."""

    def __init__(self, db: Path | None = None):
        self.db = db or (_data_dir() / "sara_control.db")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS privileged_mutations(
                        bridge TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        request_hash TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result_json TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(bridge,idempotency_key)
                    )"""
                )
        try:
            os.chmod(self.db, 0o600)
        except OSError:
            pass

    @staticmethod
    def _record(row: sqlite3.Row | None) -> MutationRecord | None:
        if row is None:
            return None
        return MutationRecord(
            bridge=row["bridge"],
            idempotency_key=row["idempotency_key"],
            request_hash=row["request_hash"],
            status=row["status"],
            result_json=row["result_json"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get(self, bridge: str, idempotency_key: str) -> MutationRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM privileged_mutations WHERE bridge=? AND idempotency_key=?",
                (bridge, idempotency_key),
            ).fetchone()
        return self._record(row)

    def reserve(self, bridge: str, idempotency_key: str, request_hash: str) -> MutationRecord:
        if not idempotency_key or len(idempotency_key) > 200:
            raise IdempotencyConflict("invalid_idempotency_key")
        now = _utc_iso()
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM privileged_mutations WHERE bridge=? AND idempotency_key=?",
                (bridge, idempotency_key),
            ).fetchone()
            if existing is not None:
                conn.rollback()
                record = self._record(existing)
                assert record is not None
                if record.request_hash != request_hash:
                    raise IdempotencyConflict("idempotency_key_reused_for_different_request")
                if record.status == "SUBMISSION_UNVERIFIED":
                    raise SubmissionUnverified("prior_submission_outcome_unverified_no_retry")
                raise IdempotencyConflict(f"idempotency_key_already_reserved:{record.status}")
            conn.execute(
                "INSERT INTO privileged_mutations VALUES(?,?,?,?,?,?,?)",
                (bridge, idempotency_key, request_hash, "RESERVED", None, now, now),
            )
            conn.commit()
        record = self.get(bridge, idempotency_key)
        assert record is not None
        return record

    def mark(self, bridge: str, idempotency_key: str, status: str, result: dict[str, Any] | None = None) -> None:
        if status not in _ALLOWED_IDEMPOTENCY_STATES:
            raise ValueError("invalid_idempotency_status")
        result_json = json.dumps(result, sort_keys=True, separators=(",", ":")) if result is not None else None
        with closing(self._connect()) as conn:
            with conn:
                cur = conn.execute(
                    "UPDATE privileged_mutations SET status=?,result_json=?,updated_at=? WHERE bridge=? AND idempotency_key=?",
                    (status, result_json, _utc_iso(), bridge, idempotency_key),
                )
                if cur.rowcount != 1:
                    raise IdempotencyConflict("idempotency_reservation_not_found")


class SourceControlBridge:
    """Read-only source-control bridge permanently bound to the canonical repository."""

    def __init__(self, *, inbound_token: str, provider_token: str, client: httpx.Client):
        self._inbound_token = inbound_token
        self._provider_token = provider_token
        self._client = client

    @classmethod
    def from_env(cls, *, client: httpx.Client | None = None) -> "SourceControlBridge":
        inbound = os.getenv("SARA_SOURCE_CONTROL_AUTH_TOKEN", "").strip()
        other = os.getenv("SARA_RAILWAY_CONTROL_AUTH_TOKEN", "").strip()
        _validate_inbound_token("SARA_SOURCE_CONTROL_AUTH_TOKEN", inbound, other_privileged=other)
        provider = _required_env("SARA_GITHUB_CONTROL_TOKEN")
        return cls(
            inbound_token=inbound,
            provider_token=provider,
            client=client or httpx.Client(base_url=GITHUB_API_BASE, timeout=15.0),
        )

    def verify_commit(self, auth_token: str, commit_sha: str) -> dict[str, str]:
        _authenticate(self._inbound_token, auth_token)
        sha = _validate_commit_sha(commit_sha)
        response = self._client.get(
            f"/repos/{BOUND_REPOSITORY}/commits/{sha}",
            headers={
                "Authorization": f"Bearer {self._provider_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if response.status_code != 200:
            raise BindingRejected(f"canonical_commit_verification_failed:{response.status_code}")
        payload = response.json()
        if payload.get("sha") != sha:
            raise BindingRejected("canonical_commit_sha_mismatch")
        return {"repository": BOUND_REPOSITORY, "commit_sha": sha, "verified": "true"}


class RailwayControlBridge:
    """Fail-closed exact-commit deploy bridge bound to one existing Railway target."""

    DEPLOYMENTS_QUERY = """
query deployments($input: DeploymentListInput!) {
  deployments(input: $input, first: 1) {
    edges { node { id status projectId serviceId environmentId createdAt } }
  }
}
""".strip()

    DEPLOY_MUTATION = """
mutation serviceInstanceDeployV2($serviceId: String!, $environmentId: String!, $commitSha: String!) {
  serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId, commitSha: $commitSha)
}
""".strip()

    def __init__(
        self,
        *,
        inbound_token: str,
        api_token: str,
        project_id: str,
        service_id: str,
        environment_id: str,
        client: httpx.Client,
        ledger: IdempotencyLedger,
    ):
        self._inbound_token = inbound_token
        self._api_token = api_token
        self.project_id = project_id
        self.service_id = service_id
        self.environment_id = environment_id
        self._client = client
        self.ledger = ledger

    @classmethod
    def from_env(
        cls,
        *,
        client: httpx.Client | None = None,
        ledger: IdempotencyLedger | None = None,
    ) -> "RailwayControlBridge":
        inbound = os.getenv("SARA_RAILWAY_CONTROL_AUTH_TOKEN", "").strip()
        other = os.getenv("SARA_SOURCE_CONTROL_AUTH_TOKEN", "").strip()
        _validate_inbound_token("SARA_RAILWAY_CONTROL_AUTH_TOKEN", inbound, other_privileged=other)
        return cls(
            inbound_token=inbound,
            api_token=_required_env("SARA_RAILWAY_API_TOKEN"),
            project_id=_required_env("SARA_RAILWAY_PROJECT_ID"),
            service_id=_required_env("SARA_RAILWAY_SERVICE_ID"),
            environment_id=_required_env("SARA_RAILWAY_ENVIRONMENT_ID"),
            client=client or httpx.Client(base_url=RAILWAY_API_BASE, timeout=20.0),
            ledger=ledger or IdempotencyLedger(),
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_token}", "Content-Type": "application/json"}

    def _current_deployment(self) -> dict[str, Any]:
        try:
            response = self._client.post(
                "/graphql/v2",
                headers=self._headers(),
                json={
                    "query": self.DEPLOYMENTS_QUERY,
                    "variables": {
                        "input": {
                            "projectId": self.project_id,
                            "serviceId": self.service_id,
                            "environmentId": self.environment_id,
                        }
                    },
                },
            )
        except httpx.TransportError as exc:
            raise BindingRejected("railway_deployment_read_failed") from exc
        if response.status_code != 200:
            raise BindingRejected(f"railway_deployment_read_failed:{response.status_code}")
        payload = response.json()
        if payload.get("errors"):
            raise BindingRejected("railway_deployment_query_rejected")
        edges = (((payload.get("data") or {}).get("deployments") or {}).get("edges") or [])
        if not edges or not isinstance(edges[0], dict) or not isinstance(edges[0].get("node"), dict):
            raise BindingRejected("railway_existing_deployment_not_found")
        node = edges[0]["node"]
        if (
            node.get("projectId") != self.project_id
            or node.get("serviceId") != self.service_id
            or node.get("environmentId") != self.environment_id
        ):
            raise BindingRejected("railway_target_binding_mismatch")
        if not isinstance(node.get("id"), str) or not node["id"]:
            raise BindingRejected("railway_deployment_id_missing")
        return node

    @staticmethod
    def _existing_idempotency_result(record: MutationRecord | None, request_hash: str) -> dict[str, Any] | None:
        if record is None:
            return None
        if record.request_hash != request_hash:
            raise IdempotencyConflict("idempotency_key_reused_for_different_request")
        if record.status == "COMPLETED" and record.result is not None:
            return record.result
        if record.status == "SUBMISSION_UNVERIFIED":
            raise SubmissionUnverified("prior_submission_outcome_unverified_no_retry")
        raise IdempotencyConflict(f"prior_idempotency_state_blocks_retry:{record.status}")

    def deploy_exact_commit(
        self,
        *,
        auth_token: str,
        commit_sha: str,
        expected_current_deployment_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        _authenticate(self._inbound_token, auth_token)
        sha = _validate_commit_sha(commit_sha)
        expected = expected_current_deployment_id.strip()
        if not expected:
            raise CompareAndSwapRejected("expected_current_deployment_id_required")
        request_payload = {
            "repository": BOUND_REPOSITORY,
            "project_id": self.project_id,
            "service_id": self.service_id,
            "environment_id": self.environment_id,
            "commit_sha": sha,
            "expected_current_deployment_id": expected,
        }
        req_hash = _request_hash(request_payload)
        existing_result = self._existing_idempotency_result(self.ledger.get("railway", idempotency_key), req_hash)
        if existing_result is not None:
            return existing_result

        current = self._current_deployment()
        if current["id"] != expected:
            raise CompareAndSwapRejected(
                f"expected_current_deployment_mismatch:{expected}:{current['id']}"
            )

        # Durable reservation commits before the external mutation is attempted.
        self.ledger.reserve("railway", idempotency_key, req_hash)

        # Recheck after reservation to narrow the remote CAS race window.
        current_after_reservation = self._current_deployment()
        if current_after_reservation["id"] != expected:
            result = {
                "status": "REJECTED",
                "reason": "expected_current_deployment_changed_after_reservation",
                "observed_deployment_id": current_after_reservation["id"],
            }
            self.ledger.mark("railway", idempotency_key, "REJECTED", result)
            raise CompareAndSwapRejected("expected_current_deployment_changed_after_reservation")

        try:
            response = self._client.post(
                "/graphql/v2",
                headers=self._headers(),
                json={
                    "query": self.DEPLOY_MUTATION,
                    "variables": {
                        "serviceId": self.service_id,
                        "environmentId": self.environment_id,
                        "commitSha": sha,
                    },
                },
            )
        except httpx.TransportError as exc:
            self.ledger.mark(
                "railway",
                idempotency_key,
                "SUBMISSION_UNVERIFIED",
                {"status": "SUBMISSION_UNVERIFIED", "reason": type(exc).__name__},
            )
            raise SubmissionUnverified("railway_submission_outcome_unverified_no_retry") from exc

        if response.status_code >= 500:
            self.ledger.mark(
                "railway",
                idempotency_key,
                "SUBMISSION_UNVERIFIED",
                {"status": "SUBMISSION_UNVERIFIED", "http_status": response.status_code},
            )
            raise SubmissionUnverified("railway_submission_server_outcome_unverified_no_retry")
        if response.status_code >= 400:
            result = {"status": "REJECTED", "http_status": response.status_code}
            self.ledger.mark("railway", idempotency_key, "REJECTED", result)
            raise PrivilegedControlError(f"railway_submission_rejected:{response.status_code}")

        payload = response.json()
        errors = payload.get("errors") or []
        deployment_id = (payload.get("data") or {}).get("serviceInstanceDeployV2")
        if errors or not isinstance(deployment_id, str) or not deployment_id:
            messages = " ".join(str(item.get("message", "")) for item in errors if isinstance(item, dict))
            if "commit not found" in messages.lower():
                result = {"status": "REJECTED", "reason": "commit_not_found"}
                self.ledger.mark("railway", idempotency_key, "REJECTED", result)
                raise PrivilegedControlError("railway_commit_not_found_no_deployment_created")
            self.ledger.mark(
                "railway",
                idempotency_key,
                "SUBMISSION_UNVERIFIED",
                {"status": "SUBMISSION_UNVERIFIED", "reason": "mutation_response_ambiguous"},
            )
            raise SubmissionUnverified("railway_mutation_response_ambiguous_no_retry")

        result = {
            "status": "COMPLETED",
            "deployment_id": deployment_id,
            "commit_sha": sha,
            "expected_previous_deployment_id": expected,
            "project_id": self.project_id,
            "service_id": self.service_id,
            "environment_id": self.environment_id,
        }
        self.ledger.mark("railway", idempotency_key, "COMPLETED", result)
        logger.info(
            "%s",
            sanitize_log_record(
                "railway_exact_commit_submitted",
                {
                    "deployment_id": deployment_id,
                    "commit_sha": sha,
                    "project_id": self.project_id,
                    "service_id": self.service_id,
                    "environment_id": self.environment_id,
                },
                secrets=(self._api_token, self._inbound_token),
            ),
        )
        return result
