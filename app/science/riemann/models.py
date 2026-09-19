from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RHProofStatus(str, Enum):
    NUMERICAL_EVIDENCE = "NUMERICAL_EVIDENCE"
    SYMBOLIC_IDENTITY = "SYMBOLIC_IDENTITY"
    CONJECTURAL_LEMMA = "CONJECTURAL_LEMMA"
    FORMAL_PROOF_CERTIFIED = "FORMAL_PROOF_CERTIFIED"


class RHEquation(BaseModel):
    equation_id: str
    latex: str
    description: str
    proof_status: RHProofStatus
    dependencies: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RHNumericalSnapshot(BaseModel):
    n: int
    d_squared: float
    theta_n: float
    truncated_j_n: float
    j_cutoff: int
    schur_next_d_squared: float | None = None
    direct_next_d_squared: float | None = None
    proof_status: RHProofStatus = RHProofStatus.NUMERICAL_EVIDENCE
    metadata: dict[str, Any] = Field(default_factory=dict)
