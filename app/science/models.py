from __future__ import annotations

from enum import Enum
from typing import Any, Literal

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


class ApplicabilityScope(str, Enum):
    UNIVERSAL_LAW = "UNIVERSAL_LAW"
    FAMILY_LEVEL = "FAMILY_LEVEL"
    ARCHITECTURE_SPECIFIC = "ARCHITECTURE_SPECIFIC"
    CONFIGURATION_SPECIFIC = "CONFIGURATION_SPECIFIC"
    EXPERIMENTAL_OBSERVATION = "EXPERIMENTAL_OBSERVATION"
    HISTORICAL_DOCUMENTATION = "HISTORICAL_DOCUMENTATION"
    HISTORICAL_RECONSTRUCTION = "HISTORICAL_RECONSTRUCTION"
    UNKNOWN = "UNKNOWN"


class CertaintyLevel(str, Enum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    INFERRED = "INFERRED"
    DISPUTED = "DISPUTED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class UniversalityStatus(str, Enum):
    UNIVERSAL_SUPPORTED = "UNIVERSAL_SUPPORTED"
    SYSTEM_DEPENDENT = "SYSTEM_DEPENDENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EngineeringState(str, Enum):
    REQUIRED = "REQUIRED"
    NOT_REQUIRED = "NOT_REQUIRED"
    SYSTEM_DEPENDENT = "SYSTEM_DEPENDENT"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ScienceClaim(BaseModel):
    claim_text: str
    provenance_class: ProvenanceClass
    evidence_status: str = "UNVERIFIED"
    applicability_scope: ApplicabilityScope = ApplicabilityScope.UNKNOWN
    certainty_level: CertaintyLevel = CertaintyLevel.UNKNOWN
    dependency_conditions: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    validation_status: str = "UNVERIFIED"
    universality_status: UniversalityStatus = UniversalityStatus.INSUFFICIENT_EVIDENCE
    certainty_ceiling: CertaintyLevel = CertaintyLevel.UNKNOWN


class TruthGateDecision(BaseModel):
    claim_text: str
    original_certainty: CertaintyLevel
    gated_certainty: CertaintyLevel
    universality_status: UniversalityStatus
    disposition: Literal["ACCEPTED", "QUALIFIED", "REJECTED"]
    reasons: list[str] = Field(default_factory=list)
    applicability_scope: ApplicabilityScope
    provenance_class: ProvenanceClass
    source_ids: list[str] = Field(default_factory=list)


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
