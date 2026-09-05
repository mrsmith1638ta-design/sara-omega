from __future__ import annotations

import os

import httpx

from .base import Specialist
from ..models import Assignment, Claim, Evidence, SpecialistResult


class PerplexitySpecialist(Specialist):
    name = "perplexity"

    def __init__(self):
        self.key = os.getenv("PERPLEXITY_API_KEY")
        self.model = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
        self.url = "https://api.perplexity.ai/v1/sonar"

    @staticmethod
    def _failure(assignment: Assignment, error: str) -> SpecialistResult:
        return SpecialistResult(
            provider="perplexity",
            role=assignment.role,
            task=assignment.task,
            success=False,
            error=error,
        )

    async def run(self, assignment: Assignment) -> SpecialistResult:
        if not self.key:
            return self._failure(assignment, "perplexity_not_configured")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are SARA-OMEGA's research specialist. Separate evidence from inference and cite current sources.",
                },
                {"role": "user", "content": assignment.task},
            ],
            "web_search_options": {"search_mode": "web"},
        }
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, dict):
                raise ValueError("malformed")
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError("malformed")
            message = choices[0].get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ValueError("malformed")
            answer = message["content"]

            search_results: list[dict[str, object]] = []
            evidence: list[Evidence] = []
            raw_search_results = data.get("search_results", [])
            if raw_search_results is not None and not isinstance(raw_search_results, list):
                raise ValueError("malformed")
            for item in raw_search_results or []:
                if not isinstance(item, dict):
                    continue
                url = item.get("url")
                if not isinstance(url, str) or not url:
                    continue
                safe = {
                    key: item.get(key)
                    for key in ("title", "url", "date", "last_updated", "snippet", "source")
                    if item.get(key) is not None
                }
                search_results.append(safe)
                evidence.append(
                    Evidence(
                        source=url,
                        title=str(item.get("title")) if item.get("title") is not None else None,
                        date=str(item.get("date")) if item.get("date") is not None else None,
                        snippet=str(item.get("snippet")) if item.get("snippet") is not None else None,
                        provider=self.name,
                    )
                )

            raw_citations = data.get("citations", [])
            if raw_citations is not None and not isinstance(raw_citations, list):
                raise ValueError("malformed")
            citations = [value for value in (raw_citations or []) if isinstance(value, str) and value]
            claim = Claim(
                provider=self.name,
                statement=answer,
                evidence=evidence,
                confidence=0.65 if evidence else 0.45,
            )
            return SpecialistResult(
                provider=self.name,
                role=assignment.role,
                task=assignment.task,
                answer=answer,
                claims=[claim],
                evidence=evidence,
                raw={
                    "model": data.get("model"),
                    "citations": citations,
                    "search_results": search_results,
                },
            )
        except httpx.TimeoutException:
            return self._failure(assignment, "perplexity_timeout")
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 403}:
                error = "perplexity_authentication_failed"
            elif status == 429:
                error = "perplexity_rate_limited"
            elif status >= 500:
                error = "perplexity_upstream_error"
            else:
                error = "perplexity_request_failed"
            return self._failure(assignment, error)
        except httpx.RequestError:
            return self._failure(assignment, "perplexity_request_failed")
        except (KeyError, IndexError, TypeError, ValueError):
            return self._failure(assignment, "perplexity_malformed_response")
        except Exception:
            return self._failure(assignment, "perplexity_internal_error")
