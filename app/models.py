from __future__ import annotations
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field

class Disposition(str, Enum):
    ALLOW = "ALLOW"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    CORROBORATED = "CORROBORATED"
    DISPUTED = "DISPUTED"
    UNSUPPORTED = "UNSUPPORTED"
    STALE = "STALE"
    UNVERIFIABLE = "UNVERIFIABLE"

class Problem(BaseModel):
    query: str
    objective: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    requested_action: str | None = None
    council: bool | None = None
    actor: str = "user"
    authority_level: int = Field(default=1, ge=0, le=5)

class ProblemMap(BaseModel):
    objective: str
    facts: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    subtasks: list[str] = Field(default_factory=list)

class Assignment(BaseModel):
    provider: str
    role: str
    task: str
    independent: bool = True

class Evidence(BaseModel):
    source: str
    title: str | None = None
    date: str | None = None
    provider: str
    snippet: str | None = None

class Claim(BaseModel):
    provider: str
    statement: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    verification: VerificationStatus = VerificationStatus.UNVERIFIABLE
    contradictions: list[str] = Field(default_factory=list)

class SpecialistResult(BaseModel):
    provider: str
    role: str
    task: str
    answer: str = ""
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    success: bool = True
    error: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

class GovernanceDecision(BaseModel):
    disposition: Disposition
    matched_rules: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)

class Verdict(BaseModel):
    decision: str
    why: str
    confidence: float = Field(ge=0, le=1)
    council_findings: list[str] = Field(default_factory=list)
    critical_assumption: str | None = None
    primary_risk: str | None = None
    evidence_gaps: list[str] = Field(default_factory=list)
    next_action: str
    governance: GovernanceDecision
    claims: list[Claim] = Field(default_factory=list)
    providers_used: list[str] = Field(default_factory=list)
    decision_id: str | None = None
