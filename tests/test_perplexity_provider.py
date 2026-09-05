from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.models import Assignment
from app.providers.perplexity import PerplexitySpecialist
import app.providers.perplexity as perplexity_module


SECRET = "pplx-secret-must-never-leak"


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("POST", "https://api.perplexity.ai/v1/sonar")

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError("upstream failure", request=self.request, response=response)

    def json(self):
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


class _FakeClient:
    response = None
    error = None

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self.error is not None:
            raise self.error
        return self.response


def _assignment() -> Assignment:
    return Assignment(provider="perplexity", role="research", task="Find current evidence.")


def _provider(monkeypatch) -> PerplexitySpecialist:
    monkeypatch.setenv("PERPLEXITY_API_KEY", SECRET)
    monkeypatch.setattr(perplexity_module.httpx, "AsyncClient", _FakeClient)
    return PerplexitySpecialist()


def _run(provider: PerplexitySpecialist):
    return asyncio.run(provider.run(_assignment()))


def test_perplexity_returns_answer_citations_and_search_results_without_secret(monkeypatch):
    provider = _provider(monkeypatch)
    _FakeClient.error = None
    _FakeClient.response = _FakeResponse(
        payload={
            "model": "sonar-pro",
            "choices": [{"message": {"content": "Grounded answer"}}],
            "citations": ["https://example.com/source"],
            "search_results": [
                {
                    "title": "Source",
                    "url": "https://example.com/source",
                    "date": "2026-09-05",
                    "snippet": "Evidence snippet",
                }
            ],
        }
    )

    result = _run(provider)

    assert result.success is True
    assert result.answer == "Grounded answer"
    assert result.raw["citations"] == ["https://example.com/source"]
    assert result.raw["search_results"][0]["url"] == "https://example.com/source"
    assert SECRET not in json.dumps(result.model_dump())


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, "perplexity_authentication_failed"),
        (403, "perplexity_authentication_failed"),
        (429, "perplexity_rate_limited"),
        (500, "perplexity_upstream_error"),
        (503, "perplexity_upstream_error"),
    ],
)
def test_perplexity_http_failures_are_safely_mapped(monkeypatch, status_code, expected_error):
    provider = _provider(monkeypatch)
    _FakeClient.error = None
    _FakeClient.response = _FakeResponse(status_code=status_code, payload={"error": SECRET})

    result = _run(provider)

    assert result.success is False
    assert result.error == expected_error
    assert SECRET not in json.dumps(result.model_dump())


def test_perplexity_timeout_is_redacted(monkeypatch):
    provider = _provider(monkeypatch)
    _FakeClient.response = None
    _FakeClient.error = httpx.TimeoutException(f"timeout carrying {SECRET}")

    result = _run(provider)

    assert result.success is False
    assert result.error == "perplexity_timeout"
    assert SECRET not in json.dumps(result.model_dump())


def test_perplexity_malformed_response_is_safely_mapped(monkeypatch):
    provider = _provider(monkeypatch)
    _FakeClient.error = None
    _FakeClient.response = _FakeResponse(payload={"model": "sonar-pro", "choices": []})

    result = _run(provider)

    assert result.success is False
    assert result.error == "perplexity_malformed_response"
    assert SECRET not in json.dumps(result.model_dump())
