from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RoadGate = Literal["GOVERNANCE", "PRIVACY", "PERFORMANCE", "RECOVERY", "MULTI-CLOUD"]


class RoadGateReviewRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=128)
    production: dict[str, Any] = Field(default_factory=dict)
    observations: list[dict[str, Any]] = Field(default_factory=list, max_length=64)
    providers: list[str] = Field(default_factory=list, max_length=16)
    probe_ms: int = Field(default=-1, ge=-1, le=30000)


class RoadGateAgent:
    """Produces concrete evidence records for ROAD's remaining release gates."""

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-road-gate-evidence",
            "role": "release-gate-evidence",
            "can_pass": False,
            "promotion_authority": "NONE",
            "execution_authority": "NONE",
        }

    def review(self, request: RoadGateReviewRequest) -> dict[str, Any]:
        production = request.production
        observed_sha = production.get("source_commit_sha")
        valid_sha = observed_sha == request.candidate_id and len(request.candidate_id) == 40
        observations = {str(item.get("id")): item for item in request.observations}
        gates = [
            self._governance(valid_sha, production, observations),
            self._privacy(valid_sha, observations),
            self._performance(valid_sha, request.probe_ms),
            self._recovery(valid_sha, production),
            self._multi_cloud(valid_sha, request.providers),
        ]
        blocked = any(item["status"] != "PASS" for item in gates)
        return {
            "service": "sara-road-gate-evidence",
            "candidate_id": request.candidate_id,
            "decision": "BLOCKED" if blocked else "READY_FOR_VERIFICATION",
            "gates": gates,
            "can_pass": False,
            "promotion_authority": "NONE",
            "execution_authority": "NONE",
            "boundary": "Produces evidence for ROAD; never promotes or executes a release.",
        }

    @staticmethod
    def _record(gate: RoadGate, status: str, detail: str) -> dict[str, Any]:
        return {"gate": gate, "status": status, "evidence_state": "VERIFIED" if status == "PASS" else "UNVERIFIED", "detail": detail}

    def _governance(self, valid: bool, production: dict[str, Any], observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
        required = {"contextdev-authorization", "madhouse-adversarial-review", "epistemic-claim-audit"}
        if valid and production.get("production_accepted") is True and all(observations.get(key, {}).get("status") == "PASS" for key in required):
            return self._record("GOVERNANCE", "PASS", "Exact deployed commit has production acceptance, Context.dev authorization, and opposition agents with no promotion authority.")
        return self._record("GOVERNANCE", "UNVERIFIED", "Governance requires exact-SHA production acceptance, Context.dev authorization, Madhouse evidence, and Epistemic evidence.")

    def _privacy(self, valid: bool, observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if valid and observations.get("contextdev-authorization", {}).get("status") == "PASS":
            return self._record("PRIVACY", "PASS", "Privacy evidence is bound to the exact candidate and the authorized Context.dev scope; no secret-bearing fields are accepted in the artifact.")
        return self._record("PRIVACY", "UNVERIFIED", "Privacy authorization evidence is missing or not exact-SHA-bound.")

    def _performance(self, valid: bool, probe_ms: int) -> dict[str, Any]:
        if valid and 0 <= probe_ms <= 4500:
            return self._record("PERFORMANCE", "PASS", f"Bounded live gate probe completed in {probe_ms} ms within ROAD's 4500 ms evidence budget.")
        return self._record("PERFORMANCE", "UNVERIFIED", "No bounded live performance probe is available within ROAD's evidence budget.")

    def _recovery(self, valid: bool, production: dict[str, Any]) -> dict[str, Any]:
        required = ("failsafe_configured", "root_on_dedicated_mount", "persistence_observed_across_boots", "chain_valid")
        if valid and all(production.get(key) is True for key in required) and production.get("persistence_status") == "PROVEN":
            return self._record("RECOVERY", "PASS", "Exact deployed commit reports configured fail-safe, dedicated mount, proven persistence across boots, and a valid retained chain.")
        return self._record("RECOVERY", "UNVERIFIED", "Recovery predicates are incomplete or do not match the exact deployed commit.")

    def _multi_cloud(self, valid: bool, providers: list[str]) -> dict[str, Any]:
        names = {provider.lower() for provider in providers}
        if valid and {"railway", "github-actions"}.issubset(names):
            return self._record("MULTI-CLOUD", "PASS", "Exact-SHA evidence spans the Railway production runtime and GitHub Actions validation provider.")
        return self._record("MULTI-CLOUD", "UNVERIFIED", "Multi-cloud evidence requires at least Railway production and GitHub Actions validation providers.")
