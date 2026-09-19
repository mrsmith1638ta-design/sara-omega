from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RiemannProofStatus(str, Enum):
    NUMERICAL_EVIDENCE = "NUMERICAL_EVIDENCE"
    SYMBOLIC_IDENTITY = "SYMBOLIC_IDENTITY"
    CANDIDATE_LEMMA = "CANDIDATE_LEMMA"
    FORMAL_PROOF_CERTIFIED = "FORMAL_PROOF_CERTIFIED"


class RiemannComputationFailure(ValueError):
    pass


class RiemannResult(BaseModel):
    statement: str
    status: RiemannProofStatus
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    certificate_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _formal_status_requires_certificate(self) -> "RiemannResult":
        if self.status == RiemannProofStatus.FORMAL_PROOF_CERTIFIED and not self.certificate_id:
            raise ValueError("formal proof status requires a certificate_id")
        return self


class RiemannRoute(RiemannResult):
    route_id: str = "riemann.baez_duarte_route"


def classify_user_facing_strength(result: RiemannResult) -> str:
    if result.status == RiemannProofStatus.FORMAL_PROOF_CERTIFIED:
        return "formal proof certified"
    if result.status == RiemannProofStatus.SYMBOLIC_IDENTITY:
        return "algebraically verified identity"
    if result.status == RiemannProofStatus.CANDIDATE_LEMMA:
        return "candidate lemma requiring proof"
    return "observed for tested finite cases"

