from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator

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

class CouncilStage(str, Enum):
    OBSERVE = "OBSERVE"
    MAP = "MAP"
    EVALUATE = "EVALUATE"
    GENERATE = "GENERATE"
    CROSS_EXAMINE = "CROSS_EXAMINE"
    STRESS_TEST = "STRESS_TEST"
    SYNTHESIZE = "SYNTHESIZE"
    GOVERN = "GOVERN"
    VERDICT = "VERDICT"
    RECORD = "RECORD"

CANONICAL_COUNCIL_STAGE_ORDER = [
    CouncilStage.OBSERVE,
    CouncilStage.MAP,
    CouncilStage.EVALUATE,
    CouncilStage.GENERATE,
    CouncilStage.CROSS_EXAMINE,
    CouncilStage.STRESS_TEST,
    CouncilStage.SYNTHESIZE,
    CouncilStage.GOVERN,
    CouncilStage.VERDICT,
    CouncilStage.RECORD,
]

class CouncilStageEvent(BaseModel):
    stage: CouncilStage
    status: str = Field(min_length=1, max_length=64)
    detail: str = Field(default="", max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=32)

class CouncilTrace(BaseModel):
    stage_order: list[CouncilStage] = Field(default_factory=lambda: list(CANONICAL_COUNCIL_STAGE_ORDER))
    completed: list[CouncilStage] = Field(default_factory=list)
    events: list[CouncilStageEvent] = Field(default_factory=list, max_length=256)
    mandatory: bool = True

    @model_validator(mode="after")
    def validate_stage_order(self) -> "CouncilTrace":
        if self.stage_order != CANONICAL_COUNCIL_STAGE_ORDER:
            raise ValueError("council_stage_order_must_be_canonical")
        canonical_index = {stage: index for index, stage in enumerate(CANONICAL_COUNCIL_STAGE_ORDER)}
        if any(stage not in canonical_index for stage in self.completed):
            raise ValueError("council_completed_stage_invalid")
        if self.completed != sorted(self.completed, key=canonical_index.__getitem__):
            raise ValueError("council_completed_stages_out_of_order")
        if len(set(self.completed)) != len(self.completed):
            raise ValueError("council_completed_stage_duplicate")
        return self

class CouncilChallenge(BaseModel):
    stage: CouncilStage
    kind: str = Field(min_length=1, max_length=64)
    finding: str = Field(min_length=1, max_length=1000)
    provider: str | None = Field(default=None, max_length=128)
    confidence_ceiling: float | None = Field(default=None, ge=0, le=1)
    evidence_gap: bool = False

class SignatureRecord(BaseModel):
    algorithm: str = Field(min_length=1, max_length=64)
    key_id: str = Field(min_length=1, max_length=256)
    signature_b64: str = Field(min_length=1, max_length=32768)
    verified: bool = False
    signer: str = Field(default="external", max_length=128)
    error: str | None = Field(default=None, max_length=512)

class IntegrityStatus(BaseModel):
    schema_version: str = "omega-verdict-ledger-v1"
    previous_record_hash: str | None = None
    current_record_hash: str | None = None
    chain_valid: bool = False
    ed25519: SignatureRecord | None = None
    ml_dsa: SignatureRecord | None = None
    durable: bool = False
    read_after_write_verified: bool = False
    status: str = "NON_DURABLE"
    error: str | None = Field(default=None, max_length=512)

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
    science_analyses: list[dict[str, Any]] = Field(default_factory=list)
    truth_gate_decisions: list[dict[str, Any]] = Field(default_factory=list)
    decision_id: str | None = None
    request_id: str | None = None
    council_trace: CouncilTrace | None = None
    integrity: IntegrityStatus = Field(default_factory=IntegrityStatus)
    supersedes_decision_id: str | None = None
