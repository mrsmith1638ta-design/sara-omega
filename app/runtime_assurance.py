from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


VerdictName = Literal["ALLOW", "REVIEW", "BLOCK"]
ClaimStatus = Literal["supported", "unsupported", "contradicted", "unavailable", "uncheckable"]


DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "deployment_state": (
        "active",
        "cloud run",
        "deployed",
        "deployment",
        "enforced",
        "live",
        "module",
        "operational",
        "registry",
        "revision",
        "running",
        "service",
        "traffic",
    ),
    "financial": (
        "10-k",
        "10-q",
        "aapl",
        "dividend",
        "earnings",
        "edgar",
        "market cap",
        "revenue",
        "sec filing",
        "stock",
        "ticker",
    ),
    "medical": (
        "adverse",
        "aspirin",
        "clinical trial",
        "contraindication",
        "diagnosis",
        "dose",
        "drug",
        "fda",
        "icd",
        "pubmed",
        "side effect",
    ),
    "legal": (
        "21 cfr",
        "case law",
        "cfr",
        "court",
        "federal register",
        "precedent",
        "regulation",
        "ruling",
        "section",
        "statute",
        "u.s.c.",
    ),
    "data_analytics": (
        "analytics",
        "anomaly",
        "average",
        "churn",
        "cohort",
        "conversion",
        "dashboard",
        "dataset",
        "data set",
        "forecast",
        "kpi",
        "median",
        "metric",
        "metrics",
        "p95",
        "p99",
        "percentile",
        "retention",
        "sample size",
        "telemetry",
        "trend",
    ),
}


class RuntimeAssuranceConfigurationError(RuntimeError):
    pass


class RuntimeAssuranceRequest(BaseModel):
    module: str = Field(min_length=1, max_length=256)
    output: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    fail_closed: bool | None = None


class ReceiptVerifyRequest(BaseModel):
    receipt: dict[str, Any]
    allow_expired: bool = False


class RuntimeAssuranceEngine:
    """Enterprise runtime assurance gate for generated AI output.

    The gate treats generated text as untrusted until checkable claims are
    compared against live module truth or configured evidence adapters.
    """

    def __init__(self, env: dict[str, str] | None = None):
        self.env = env if env is not None else os.environ

    def router_state(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        context_adapters = context.get("evidence_adapters") or {}
        domains = []
        for domain, keywords in DOMAIN_KEYWORDS.items():
            url = self._adapter_url(domain)
            domains.append(
                {
                    "domain": domain,
                    "active": bool(url or domain in context_adapters),
                    "url": url,
                    "priority": 10 if domain == "deployment_state" else 5,
                    "required": False,
                    "keywords": list(keywords),
                }
            )
        domains.append(
            {
                "domain": "general_knowledge",
                "active": self._env_bool("SARA_GENERAL_KNOWLEDGE_ASSURANCE", False),
                "url": self.env.get("SARA_EVIDENCE_GENERAL_KNOWLEDGE_URL", ""),
                "priority": 1,
                "required": False,
                "keywords": [],
            }
        )
        return {
            "service": "sara-runtime-assurance",
            "policy": "fail_closed_claim_suppression",
            "domains": domains,
        }

    async def verify_output(self, request: RuntimeAssuranceRequest) -> dict[str, Any]:
        fail_closed = request.fail_closed
        if fail_closed is None:
            fail_closed = self._env_bool("SARA_RUNTIME_ASSURANCE_FAIL_CLOSED", True)

        claims = self._extract_claims(request.output)
        router = self.router_state(request.context)
        active_domains = [d["domain"] for d in router["domains"] if d["active"]]
        live_truth = self._live_module_truth(request.context)

        claim_results = []
        for claim in claims:
            domains = self._classify_claim(claim)
            evidence_results: list[dict[str, Any]] = []
            if "deployment_state" in domains:
                evidence_results.extend(self._check_live_module_truth(claim, live_truth))

            for domain in domains:
                if domain == "deployment_state":
                    continue
                evidence_results.append(await self._query_adapter(domain, claim, request))

            status = self._claim_status(domains, evidence_results)
            claim_results.append(
                {
                    "claim": claim,
                    "domains": domains,
                    "status": status,
                    "evidence_results": evidence_results,
                    "reasons": self._claim_reasons(status, domains, evidence_results, fail_closed),
                }
            )

        verdict, action, explanation = self._overall_verdict(claim_results, fail_closed)
        receipt = self._audit_receipt(
            module=request.module,
            verdict=verdict,
            action=action,
            claim_results=claim_results,
            router=router,
            live_truth=live_truth,
        )

        return {
            "service": "sara-runtime-assurance",
            "module": request.module,
            "verdict": verdict,
            "action": action,
            "explanation": explanation,
            "fail_closed": fail_closed,
            "active_evidence_domains": active_domains,
            "claims": claim_results,
            "audit_receipt": receipt,
            "suppression": {
                "applied": verdict == "BLOCK",
                "text": (
                    "SARA cannot provide that response because runtime assurance "
                    "could not verify one or more checkable claims."
                    if verdict == "BLOCK"
                    else ""
                ),
            },
        }

    def verify_receipt(self, request: ReceiptVerifyRequest) -> dict[str, Any]:
        receipt = dict(request.receipt)
        signature = str(receipt.pop("signature", ""))
        expected = self._signature(receipt)
        signature_ok = hmac.compare_digest(signature, expected)
        expires_at = str(receipt.get("expires_at", ""))
        expired = False
        if expires_at:
            try:
                expired = datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < self._now()
            except ValueError:
                expired = True
        return {
            "valid": signature_ok and (request.allow_expired or not expired),
            "signature_ok": signature_ok,
            "expired": expired,
            "receipt_id": receipt.get("receipt_id"),
        }

    def _adapter_url(self, domain: str) -> str:
        env_domain = domain.upper()
        names = [
            f"SARA_EVIDENCE_{env_domain}_URL",
            f"EVIDENCE_{env_domain}_URL",
        ]
        if domain == "deployment_state":
            names.extend(("SARA_LIVE_MODULE_TRUTH_URL", "LIVE_MODULE_TRUTH_URL", "EVIDENCE_STATE_URL"))
        for name in names:
            value = self.env.get(name, "").strip()
            if value:
                return value.rstrip("/")
        return ""

    def _adapter_path(self, domain: str) -> str:
        env_domain = domain.upper()
        return self.env.get(f"SARA_EVIDENCE_{env_domain}_PATH", "/verify").strip() or "/verify"

    def _env_bool(self, name: str, default: bool) -> bool:
        value = self.env.get(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _extract_claims(self, output: str) -> list[str]:
        pieces = re.split(r"(?<=[.!?])\s+|\n+", output.strip())
        claims = [p.strip(" \t\r\n-") for p in pieces if p.strip(" \t\r\n-")]
        return claims or [output.strip()]

    def _classify_claim(self, claim: str) -> list[str]:
        lower = claim.lower()
        domains = [
            domain
            for domain, keywords in DOMAIN_KEYWORDS.items()
            if any(keyword in lower for keyword in keywords)
        ]
        if re.search(r"\bsara-[a-z0-9-]+\b", lower) and "deployment_state" not in domains:
            domains.append("deployment_state")
        return domains

    def _live_module_truth(self, context: dict[str, Any]) -> dict[str, Any]:
        truth = dict(context.get("live_module_truth") or {})
        modules = truth.get("modules", context.get("live_modules", {}))
        normalized_modules: dict[str, bool] = {}
        if isinstance(modules, list):
            normalized_modules = {str(name).lower(): True for name in modules}
        elif isinstance(modules, dict):
            for name, value in modules.items():
                if isinstance(value, dict):
                    live_value = value.get("live", value.get("active", value.get("running")))
                    normalized_modules[str(name).lower()] = bool(live_value)
                else:
                    normalized_modules[str(name).lower()] = bool(value)

        enforced = truth.get("enforced_modules", context.get("enforced_modules", []))
        if isinstance(enforced, dict):
            enforced_modules = [str(k).lower() for k, v in enforced.items() if v]
        else:
            enforced_modules = [str(v).lower() for v in enforced]

        return {
            "source": truth.get("source", context.get("live_module_truth_source", "runtime_context")),
            "live_count": truth.get("live_count", context.get("live_module_count")),
            "historical_count": truth.get("historical_count", context.get("historical_module_count")),
            "modules": normalized_modules,
            "enforced_modules": enforced_modules,
            "enforcement_count": truth.get("enforcement_count", context.get("enforcement_count", len(enforced_modules))),
        }

    def _check_live_module_truth(self, claim: str, truth: dict[str, Any]) -> list[dict[str, Any]]:
        lower = claim.lower()
        results: list[dict[str, Any]] = []
        asserts_live = self._asserts_live(lower)
        asserts_not_live = bool(re.search(r"\b(?:not|no longer|is not|isn't|are not|aren't)\s+(?:live|running|deployed|operational|active)\b", lower))
        modules = sorted(set(re.findall(r"\bsara-[a-z0-9-]+\b", lower)))
        module_truth: dict[str, bool] = truth.get("modules") or {}

        for module in modules:
            known_live = module_truth.get(module)
            if known_live is None:
                results.append(
                    {
                        "domain": "deployment_state",
                        "source": truth.get("source"),
                        "status": "unsupported",
                        "confidence": 0.4,
                        "detail": f"{module} is not present in live module truth.",
                    }
                )
            elif asserts_live and not known_live:
                results.append(
                    {
                        "domain": "deployment_state",
                        "source": truth.get("source"),
                        "status": "contradicted",
                        "confidence": 0.95,
                        "detail": f"Claim asserts {module} is live, but live module truth marks it not live.",
                    }
                )
            elif asserts_not_live and known_live:
                results.append(
                    {
                        "domain": "deployment_state",
                        "source": truth.get("source"),
                        "status": "contradicted",
                        "confidence": 0.95,
                        "detail": f"Claim asserts {module} is not live, but live module truth marks it live.",
                    }
                )
            else:
                results.append(
                    {
                        "domain": "deployment_state",
                        "source": truth.get("source"),
                        "status": "supported",
                        "confidence": 0.85,
                        "detail": f"Live module truth contains {module}.",
                    }
                )

        count_results = self._check_module_counts(lower, truth)
        results.extend(count_results)
        if not results and not truth.get("modules") and truth.get("live_count") is None:
            results.append(
                {
                    "domain": "deployment_state",
                    "source": truth.get("source"),
                    "status": "unavailable",
                    "confidence": 0.0,
                    "detail": "No live module truth was supplied for a deployment-state claim.",
                }
            )
        return results

    def _asserts_live(self, lower: str) -> bool:
        if re.search(r"\b(?:not|no longer|is not|isn't|are not|aren't)\s+(?:live|running|deployed|operational|active)\b", lower):
            return False
        return bool(re.search(r"\b(?:live|running|deployed|operational|active)\b", lower))

    def _check_module_counts(self, lower: str, truth: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for match in re.finditer(r"\b(all\s+)?(\d{1,4})\s+(?:sara[- ]*)?modules?\b", lower):
            all_claim = bool(match.group(1))
            claimed_count = int(match.group(2))
            live_count = self._int_or_none(truth.get("live_count"))
            historical_count = self._int_or_none(truth.get("historical_count"))
            enforcement_count = self._int_or_none(truth.get("enforcement_count"))
            mentions_live = bool(re.search(r"\b(?:live|running|deployed|operational|active)\b", lower))
            mentions_enforcement = bool(re.search(r"\b(?:enforced|enforcement|protected|covered|wrapped)\b", lower))
            mentions_historical = "historical" in lower or "registry" in lower or "inventory" in lower

            if mentions_historical and historical_count == claimed_count and not mentions_live and not mentions_enforcement:
                results.append(
                    {
                        "domain": "deployment_state",
                        "source": truth.get("source"),
                        "status": "supported",
                        "confidence": 0.9,
                        "detail": f"Historical module inventory count is {historical_count}.",
                    }
                )
            if (all_claim or mentions_live) and live_count is not None and live_count != claimed_count:
                results.append(
                    {
                        "domain": "deployment_state",
                        "source": truth.get("source"),
                        "status": "contradicted",
                        "confidence": 0.95,
                        "detail": f"Claim implies {claimed_count} live modules, but live module truth reports {live_count}.",
                    }
                )
            if mentions_enforcement and enforcement_count is not None and enforcement_count != claimed_count:
                results.append(
                    {
                        "domain": "deployment_state",
                        "source": truth.get("source"),
                        "status": "contradicted",
                        "confidence": 0.95,
                        "detail": f"Claim implies enforcement across {claimed_count} modules, but enforcement truth reports {enforcement_count}.",
                    }
                )
        return results

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    async def _query_adapter(
        self, domain: str, claim: str, request: RuntimeAssuranceRequest
    ) -> dict[str, Any]:
        context_adapters = request.context.get("evidence_adapters") or {}
        if domain in context_adapters:
            return self._normalize_adapter_result(domain, context_adapters[domain])

        for item in request.evidence:
            if str(item.get("domain", "")).lower() == domain:
                return self._normalize_adapter_result(domain, item)

        url = self._adapter_url(domain)
        if not url:
            return {
                "domain": domain,
                "source": "adapter_registry",
                "status": "unavailable",
                "confidence": 0.0,
                "detail": f"No {domain} evidence adapter is configured.",
            }

        try:
            import httpx

            payload = {"claim": claim, "module": request.module, "context": request.context}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{url}{self._adapter_path(domain)}", json=payload)
                response.raise_for_status()
                data = response.json()
            return self._normalize_adapter_result(domain, data)
        except Exception as exc:
            return {
                "domain": domain,
                "source": url,
                "status": "unavailable",
                "confidence": 0.0,
                "detail": f"{domain} evidence adapter failed: {exc}",
            }

    def _normalize_adapter_result(self, domain: str, result: Any) -> dict[str, Any]:
        if isinstance(result, list):
            result = {"evidence": result, "verdict": "supported" if result else "unsupported"}
        if not isinstance(result, dict):
            return {
                "domain": domain,
                "source": "adapter",
                "status": "unavailable",
                "confidence": 0.0,
                "detail": "Adapter returned an unsupported response shape.",
            }

        raw_status = str(result.get("status", result.get("verdict", result.get("support", "")))).lower()
        if raw_status in {"true", "verified", "corroborated", "supported", "support", "allow"}:
            status: ClaimStatus = "supported"
        elif raw_status in {"false", "contradicted", "contradiction", "disputed", "block"}:
            status = "contradicted"
        elif raw_status in {"unavailable", "error", "failed", "timeout"} or result.get("error"):
            status = "unavailable"
        elif raw_status in {"unsupported", "unverifiable", "unknown", "review"}:
            status = "unsupported"
        else:
            status = "unsupported"

        return {
            "domain": domain,
            "source": result.get("source", result.get("adapter", domain)),
            "status": status,
            "confidence": self._confidence(result.get("confidence", 0.5 if status == "supported" else 0.4)),
            "detail": result.get("detail", result.get("explanation", "")),
            "evidence": result.get("evidence", []),
        }

    def _confidence(self, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.5
        return max(0.0, min(1.0, number))

    def _claim_status(self, domains: list[str], evidence_results: list[dict[str, Any]]) -> ClaimStatus:
        if not domains:
            return "uncheckable"
        statuses = {str(item.get("status")) for item in evidence_results}
        if "contradicted" in statuses:
            return "contradicted"
        if "supported" in statuses:
            return "supported"
        if "unavailable" in statuses:
            return "unavailable"
        return "unsupported"

    def _claim_reasons(
        self,
        status: ClaimStatus,
        domains: list[str],
        evidence_results: list[dict[str, Any]],
        fail_closed: bool,
    ) -> list[str]:
        if status == "supported":
            return ["At least one configured evidence source supports the checkable claim."]
        if status == "contradicted":
            return [str(item.get("detail")) for item in evidence_results if item.get("status") == "contradicted"]
        if status == "unavailable":
            return [str(item.get("detail")) for item in evidence_results if item.get("status") == "unavailable"]
        if status == "unsupported" and fail_closed:
            return [f"No configured evidence source supported this {', '.join(domains)} claim."]
        if status == "uncheckable":
            return ["No regulated evidence domain matched this claim."]
        return ["Claim requires review."]

    def _overall_verdict(
        self, claim_results: list[dict[str, Any]], fail_closed: bool
    ) -> tuple[VerdictName, str, str]:
        if any(c["status"] == "contradicted" for c in claim_results):
            return "BLOCK", "suppress", "One or more checkable claims contradicted live evidence."
        if fail_closed and any(c["status"] in {"unsupported", "unavailable"} for c in claim_results):
            return "BLOCK", "suppress", "One or more checkable claims lacked required evidence under fail-closed policy."
        if any(c["status"] == "uncheckable" for c in claim_results):
            return "REVIEW", "escalate", "Some claims did not match a configured evidence domain."
        return "ALLOW", "render", "All checkable claims were supported by configured evidence."

    def _audit_receipt(
        self,
        module: str,
        verdict: VerdictName,
        action: str,
        claim_results: list[dict[str, Any]],
        router: dict[str, Any],
        live_truth: dict[str, Any],
    ) -> dict[str, Any]:
        now = self._now()
        ttl = int(self.env.get("SARA_RUNTIME_ASSURANCE_RECEIPT_TTL_SECONDS", "600"))
        unsigned = {
            "version": "sara_runtime_assurance_receipt_v1",
            "module": module,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat().replace("+00:00", "Z"),
            "verdict": verdict,
            "action": action,
            "policy": "fail_closed_claim_suppression",
            "claim_hashes": [self._sha256(c["claim"]) for c in claim_results],
            "evidence_hash": self._sha256_json([c["evidence_results"] for c in claim_results]),
            "router_hash": self._sha256_json(router),
            "live_module_truth_hash": self._sha256_json(live_truth),
            "attack_vector_checks": [
                "contradicted_live_module_claim",
                "missing_adapter_fail_closed",
                "adapter_verdict_contradiction",
                "data_analytics_metric_claim_without_dataset",
                "receipt_tamper_resistance",
            ],
            "source_cross_reference": [
                "Governance Core hard boundaries",
                "OMEGA Council evidence insufficiency rule",
                "Triangle expansion data analytics specialist",
                "Decision Ledger auditability",
                "Provider output is not verified fact",
            ],
        }
        unsigned["receipt_id"] = self._sha256_json(unsigned)
        signed = dict(unsigned)
        signed["signature"] = self._signature(unsigned)
        return signed

    def _signature(self, payload: dict[str, Any]) -> str:
        secret = self.env.get("SARA_RUNTIME_ASSURANCE_SECRET", "").strip()
        if not secret:
            raise RuntimeAssuranceConfigurationError(
                "SARA_RUNTIME_ASSURANCE_SECRET must be set before runtime assurance can issue or verify receipts."
            )
        digest = hmac.new(secret.encode("utf-8"), self._canonical(payload), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def _sha256(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _sha256_json(self, value: Any) -> str:
        return hashlib.sha256(self._canonical(value)).hexdigest()

    def _canonical(self, value: Any) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
