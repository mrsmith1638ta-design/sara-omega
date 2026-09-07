from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProvenanceClass(str, Enum):
    DOCUMENTED_ANCIENT = "DOCUMENTED_ANCIENT"
    HISTORICALLY_COMPATIBLE_RECONSTRUCTION = "HISTORICALLY_COMPATIBLE_RECONSTRUCTION"
    MODERN_ENGINEERING_DERIVATION = "MODERN_ENGINEERING_DERIVATION"
    ESTABLISHED_PHYSICS = "ESTABLISHED_PHYSICS"
    DOCUMENTED_TECHNOLOGY = "DOCUMENTED_TECHNOLOGY"
    ENGINEERING_MODEL = "ENGINEERING_MODEL"
    EXPERIMENTAL_TECHNOLOGY = "EXPERIMENTAL_TECHNOLOGY"
    SIMULATION_OR_HYPOTHESIS = "SIMULATION_OR_HYPOTHESIS"


class ScienceCalculation(BaseModel):
    equation_id: str
    variables: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    inputs: dict[str, float | int | str] = Field(default_factory=dict)
    result: Any = None
    provenance_class: ProvenanceClass
    evidence_status: str = "UNVERIFIED"
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    validation_status: str = "UNVERIFIED"


class ScienceAnalysis(BaseModel):
    domain: str
    summary: str
    calculations: list[ScienceCalculation] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    execution_authority: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
