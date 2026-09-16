from pydantic import BaseModel, Field
from typing import Any

class RecoveryRequest(BaseModel):
    context: dict[str,Any] = Field(default_factory=dict)
    approved: bool = False

class CounterfactualRequest(BaseModel):
    baseline: dict[str,Any]
    changes: dict[str,Any]

class JuryOpinionInput(BaseModel):
    model_id: str
    conclusion: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)

class JuryRequest(BaseModel):
    opinions: list[JuryOpinionInput] = Field(min_length=1)

class IncidentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    severity: str = Field(pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    affected: list[str] = Field(default_factory=list, max_length=100)

class TwinObservationRequest(BaseModel):
    entity_id: str = Field(min_length=1, max_length=200)
    state: dict[str,Any]
    verified: bool
    source: str = Field(min_length=1, max_length=200)
