from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from integrity_patch import PATCH_VERSION, router as integrity_router

PROTOCOL_ID = "SARA-GTP-001"
PROTOCOL_NAME = "SARA Global Truth Protocol"
app = FastAPI(
    title=PROTOCOL_NAME,
    version="1.3.0",
    description="Global anti-hallucination, anti-fluff, anti-fabrication governance layer for SARA with post-quantum integrity evidence.",
)
app.include_router(integrity_router)

class TruthCheckRequest(BaseModel):
    module_id: str = Field(default="unknown")
    user_directive: str = Field(default="")
    proposed_response: str = Field(default="")
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    context: Optional[str] = None
    requires_current_facts: bool = False
    requires_action: bool = False

class TruthCheckResponse(BaseModel):
    protocol_id: str
    protocol_name: str
    status: str
    allowed: bool
    timestamp: str
    module_id: str
    violations: list[str]
    required_corrections: list[str]
    context_verification: str
    assumption_disclosure: list[str]
    uncertainty_statement_required: bool
    clarification_required: bool
    clarification_questions: list[str]
    final_instruction: str

GLOBAL_RULES = [
    "Hallucinations are prohibited.",
    "Lies and fabricated facts are prohibited.",
    "Unsupported certainty is prohibited.",
    "Fluff, filler, and evasive language are prohibited.",
    "If evidence is missing, say what is unknown.",
    "If current facts are required, live verification is required before specific claims.",
    "If ambiguity exists, ask for clarification before action.",
    "If assumptions are required, disclose them before proceeding.",
    "If an error is identified, acknowledge it immediately and correct it.",
    "Every significant SARA action must preserve auditability.",
]

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def detect_violations(req: TruthCheckRequest):
    text = (req.proposed_response or "").strip()
    directive = (req.user_directive or "").strip()
    violations, corrections, questions = [], [], []
    if not text:
        violations.append("EMPTY_RESPONSE")
        corrections.append("Provide a direct, grounded response or ask a specific clarification question.")
    vague = ["it seems", "might be", "possibly", "perhaps", "as an ai", "i think", "probably", "could be", "in general terms"]
    if text and sum(1 for phrase in vague if phrase in text.lower()) >= 3:
        violations.append("EXCESSIVE_VAGUENESS_OR_FLUFF")
        corrections.append("Remove filler and state only verified facts, explicit assumptions, or clear uncertainty.")
    certainty = ["guaranteed", "certainly", "undeniably", "without question", "definitely true", "proven"]
    if any(phrase in text.lower() for phrase in certainty) and not req.evidence:
        violations.append("UNSUPPORTED_CERTAINTY")
        corrections.append("Remove certainty or attach evidence.")
    if req.requires_current_facts and not req.evidence:
        violations.append("CURRENT_FACTS_WITHOUT_LIVE_EVIDENCE")
        corrections.append("Perform live verification before quoting current facts.")
    if req.requires_action and not directive:
        violations.append("ACTION_WITHOUT_DIRECTIVE")
        corrections.append("Do not act without a clear directive.")
    ambiguous = {"fix it", "do it", "build this", "run it", "deploy it", "make it work"}
    if directive.lower() in ambiguous or (directive and len(directive.split()) < 4 and req.requires_action):
        violations.append("AMBIGUOUS_DIRECTIVE")
        corrections.append("Ask for the target service, file, or deployment path before acting.")
        questions.append("Which exact service, file, or module should this action target?")
    return violations, corrections, questions

def evaluate(req: TruthCheckRequest) -> TruthCheckResponse:
    violations, corrections, questions = detect_violations(req)
    assumptions = req.assumptions or ["No hidden assumptions may be used. If an assumption is needed, it must be stated first."]
    allowed = not violations
    return TruthCheckResponse(
        protocol_id=PROTOCOL_ID,
        protocol_name=PROTOCOL_NAME,
        status="truth_protocol_passed" if allowed else "blocked_until_corrected",
        allowed=allowed,
        timestamp=now(),
        module_id=req.module_id,
        violations=violations,
        required_corrections=corrections,
        context_verification=req.context or "Global SARA ecosystem context requires truth, evidence, clarity, and auditability.",
        assumption_disclosure=assumptions,
        uncertainty_statement_required=bool(req.requires_current_facts and not req.evidence),
        clarification_required="AMBIGUOUS_DIRECTIVE" in violations,
        clarification_questions=questions,
        final_instruction="Proceed only with grounded, factual, non-fluffy output." if allowed else "Do not proceed until violations are corrected.",
    )

@app.get("/")
def root() -> dict[str, Any]:
    return {
        "status": "ok", "service": "sara-global-truth-protocol", "protocol_id": PROTOCOL_ID,
        "patch": PATCH_VERSION,
        "routes": ["/health", "/manifest", "/truth/check", "/truth/rules", "/v1/integrity/sign-state", "/v1/integrity/verify-state", "/v1/integrity/chain"],
    }

@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "sara-global-truth-protocol", "protocol_id": PROTOCOL_ID, "patch": PATCH_VERSION, "timestamp": now()}

@app.get("/manifest")
def manifest() -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID, "name": PROTOCOL_NAME, "scope": "GLOBAL_SARA_ECOSYSTEM", "status": "ACTIVE",
        "quantum_integrity": {"status": "ACTIVE", "hash": "SHA3-512", "signature": "ML-DSA-87", "mode": "liboqs_native", "append_only": True},
        "timestamp": now(),
    }

@app.get("/truth/rules")
def truth_rules() -> dict[str, Any]:
    return {"protocol_id": PROTOCOL_ID, "rules": GLOBAL_RULES}

@app.post("/truth/check")
def truth_check(req: TruthCheckRequest) -> TruthCheckResponse:
    return evaluate(req)
