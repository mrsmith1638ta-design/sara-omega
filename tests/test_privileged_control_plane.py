from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.control_plane import (
    AuthenticationRejected,
    BOUND_REPOSITORY,
    CompareAndSwapRejected,
    IdempotencyConflict,
    IdempotencyLedger,
    RailwayControlBridge,
    SourceControlBridge,
    SubmissionUnverified,
    sanitize_log_record,
)


def _base_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OWNER_TOKEN", "owner-token")
    monkeypatch.setenv("GPT_ACTION_TOKEN", "gpt-action-token")
    monkeypatch.setenv("TEST_TOKEN", "test-token")
    monkeypatch.setenv("SARA_SOURCE_CONTROL_AUTH_TOKEN", "source-control-inbound")
    monkeypatch.setenv("SARA_GITHUB_CONTROL_TOKEN", "github-provider-token")
    monkeypatch.setenv("SARA_RAILWAY_CONTROL_AUTH_TOKEN", "railway-control-inbound")
    monkeypatch.setenv("SARA_RAILWAY_API_TOKEN", "railway-provider-token")
    monkeypatch.setenv("SARA_RAILWAY_PROJECT_ID", "project-fixed")
    monkeypatch.setenv("SARA_RAILWAY_SERVICE_ID", "service-fixed")
    monkeypatch.setenv("SARA_RAILWAY_ENVIRONMENT_ID", "environment-fixed")


def test_privileged_tokens_must_be_distinct_from_public_action_and_test_tokens(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("SARA_SOURCE_CONTROL_AUTH_TOKEN", "gpt-action-token")
    with pytest.raises(AuthenticationRejected):
        SourceControlBridge.from_env()

    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("SARA_RAILWAY_CONTROL_AUTH_TOKEN", "test-token")
    with pytest.raises(AuthenticationRejected):
        RailwayControlBridge.from_env()

    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("SARA_RAILWAY_CONTROL_AUTH_TOKEN", "owner-token")
    with pytest.raises(AuthenticationRejected):
        RailwayControlBridge.from_env()


def test_source_control_bridge_is_hard_bound_to_canonical_repository(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == f"/repos/{BOUND_REPOSITORY}/commits/" + "a" * 40
        assert request.headers["authorization"] == "Bearer github-provider-token"
        return httpx.Response(200, json={"sha": "a" * 40})

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    bridge = SourceControlBridge.from_env(client=client)

    result = bridge.verify_commit("source-control-inbound", "a" * 40)

    assert result["repository"] == "mrsmith1638ta-design/sara-omega"
    assert result["commit_sha"] == "a" * 40
    assert len(seen) == 1


def test_railway_compare_and_swap_blocks_before_mutation(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)
    mutations = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal mutations
        body = json.loads(request.content)
        if "deployments" in body["query"]:
            assert body["variables"]["input"] == {
                "projectId": "project-fixed",
                "serviceId": "service-fixed",
                "environmentId": "environment-fixed",
            }
            return httpx.Response(
                200,
                json={"data": {"deployments": {"edges": [{"node": {
                    "id": "dep-current",
                    "status": "SUCCESS",
                    "projectId": "project-fixed",
                    "serviceId": "service-fixed",
                    "environmentId": "environment-fixed",
                    "createdAt": "2026-09-04T12:00:00Z",
                }}]}}},
            )
        mutations += 1
        return httpx.Response(500)

    client = httpx.Client(base_url="https://backboard.railway.com", transport=httpx.MockTransport(handler))
    bridge = RailwayControlBridge.from_env(client=client)

    with pytest.raises(CompareAndSwapRejected):
        bridge.deploy_exact_commit(
            auth_token="railway-control-inbound",
            commit_sha="b" * 40,
            expected_current_deployment_id="different-deployment",
            idempotency_key="idem-cas-1",
        )

    assert mutations == 0


def test_railway_reserves_idempotency_before_exact_commit_mutation(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)
    ledger = IdempotencyLedger()
    query_count = 0
    mutation_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal query_count, mutation_count
        body = json.loads(request.content)
        if "serviceInstanceDeployV2" not in body["query"]:
            query_count += 1
            return httpx.Response(
                200,
                json={"data": {"deployments": {"edges": [{"node": {
                    "id": "dep-current",
                    "status": "SUCCESS",
                    "projectId": "project-fixed",
                    "serviceId": "service-fixed",
                    "environmentId": "environment-fixed",
                    "createdAt": "2026-09-04T12:00:00Z",
                }}]}}},
            )

        mutation_count += 1
        record = ledger.get("railway", "idem-deploy-1")
        assert record is not None
        assert record.status == "RESERVED"
        assert body["variables"] == {
            "serviceId": "service-fixed",
            "environmentId": "environment-fixed",
            "commitSha": "c" * 40,
        }
        return httpx.Response(200, json={"data": {"serviceInstanceDeployV2": "dep-new"}})

    client = httpx.Client(base_url="https://backboard.railway.com", transport=httpx.MockTransport(handler))
    bridge = RailwayControlBridge.from_env(client=client, ledger=ledger)

    result = bridge.deploy_exact_commit(
        auth_token="railway-control-inbound",
        commit_sha="c" * 40,
        expected_current_deployment_id="dep-current",
        idempotency_key="idem-deploy-1",
    )

    assert result["deployment_id"] == "dep-new"
    assert result["commit_sha"] == "c" * 40
    assert ledger.get("railway", "idem-deploy-1").status == "COMPLETED"
    assert query_count == 2  # CAS is rechecked after reservation immediately before mutation.
    assert mutation_count == 1


def test_uncertain_railway_submission_is_terminal_and_never_auto_retried(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)
    ledger = IdempotencyLedger()
    mutation_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal mutation_count
        body = json.loads(request.content)
        if "serviceInstanceDeployV2" not in body["query"]:
            return httpx.Response(
                200,
                json={"data": {"deployments": {"edges": [{"node": {
                    "id": "dep-current",
                    "status": "SUCCESS",
                    "projectId": "project-fixed",
                    "serviceId": "service-fixed",
                    "environmentId": "environment-fixed",
                    "createdAt": "2026-09-04T12:00:00Z",
                }}]}}},
            )
        mutation_count += 1
        raise httpx.ReadTimeout("response outcome unknown", request=request)

    client = httpx.Client(base_url="https://backboard.railway.com", transport=httpx.MockTransport(handler))
    bridge = RailwayControlBridge.from_env(client=client, ledger=ledger)

    kwargs = dict(
        auth_token="railway-control-inbound",
        commit_sha="d" * 40,
        expected_current_deployment_id="dep-current",
        idempotency_key="idem-uncertain-1",
    )
    with pytest.raises(SubmissionUnverified):
        bridge.deploy_exact_commit(**kwargs)

    assert ledger.get("railway", "idem-uncertain-1").status == "SUBMISSION_UNVERIFIED"
    assert mutation_count == 1

    with pytest.raises(SubmissionUnverified):
        bridge.deploy_exact_commit(**kwargs)
    assert mutation_count == 1


def test_bounded_log_sanitizer_redacts_secret_values_and_secret_fields():
    secret = "railway-provider-super-secret-value"
    rendered = sanitize_log_record(
        "railway_submission",
        {
            "authorization": f"Bearer {secret}",
            "note": "prefix " + secret + " suffix",
            "token": secret,
            "payload": "x" * 5000,
        },
        secrets=[secret],
        max_chars=1024,
    )

    assert secret not in rendered
    assert "Bearer" not in rendered
    assert len(rendered) <= 1024


def test_chatgpt_action_schema_does_not_expose_privileged_controls():
    schema = Path("chatgpt-gpt-action.yaml").read_text(encoding="utf-8")
    lowered = schema.lower()
    assert "source-control" not in lowered
    assert "railway-control" not in lowered
    assert "deploy_exact_commit" not in lowered
