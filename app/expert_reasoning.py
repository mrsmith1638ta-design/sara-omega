from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class ExpertLensKind(str, Enum):
    RESEARCH_PHD = "research_phd_method"
    LEGAL_JD = "legal_jd_method"
    EDUCATION_EDD = "education_edd_method"
    AI_RESEARCH_PHD = "ai_research_phd_method"
    INDUSTRY_DOMAIN = "industry_domain_method"


@dataclass(frozen=True)
class ExpertLens:
    lens_id: str
    kind: ExpertLensKind
    title: str
    method_steps: tuple[str, ...]
    triggers: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "lens_id": self.lens_id,
            "kind": self.kind.value,
            "title": self.title,
            "method_steps": list(self.method_steps),
            "limitations": list(self.limitations),
        }


CORE_LENSES: tuple[ExpertLens, ...] = (
    ExpertLens(
        lens_id="phd-research",
        kind=ExpertLensKind.RESEARCH_PHD,
        title="Doctoral research-method lens",
        method_steps=(
            "frame the research question and competing hypotheses",
            "identify source quality, provenance, recency, and evidence gaps",
            "separate correlation, prediction, mechanism, and causation",
            "test falsifiability and alternative explanations",
            "evaluate methods, statistics, uncertainty, and reproducibility",
            "state limitations and what evidence would change the conclusion",
        ),
        limitations=(
            "methodology analogue only; SARA does not claim a human PhD credential",
            "no methodology lens substitutes for domain evidence or qualified human review",
        ),
    ),
    ExpertLens(
        lens_id="jd-legal",
        kind=ExpertLensKind.LEGAL_JD,
        title="Juris Doctor legal-analysis lens",
        method_steps=(
            "identify jurisdiction, issue, parties, posture, and controlling authority",
            "rank constitutions, statutes, regulations, cases, contracts, and agency guidance by authority",
            "apply governing rules to the stated facts",
            "surface counterarguments, exceptions, remedies, procedure, and uncertainty",
            "distinguish legal requirements from policy preferences and business risk",
            "flag when licensed counsel or jurisdiction-specific research is required",
        ),
        triggers=(
            "law", "legal", "statute", "regulation", "contract", "liability", "court",
            "compliance", "attorney", "jurisdiction", "patent", "copyright", "privacy",
        ),
        limitations=(
            "methodology analogue only; SARA does not claim a JD or law license",
            "not legal advice and not a substitute for licensed counsel",
        ),
    ),
    ExpertLens(
        lens_id="edd-applied",
        kind=ExpertLensKind.EDUCATION_EDD,
        title="Doctor of Education applied-systems lens",
        method_steps=(
            "define learners, stakeholders, organizational context, and desired outcomes",
            "identify implementation constraints, accessibility, equity, ethics, and change-management factors",
            "select measurable learning or organizational outcomes",
            "compare interventions against evidence and local context",
            "design formative and summative evaluation",
            "iterate from measured outcomes rather than assumed effectiveness",
        ),
        triggers=(
            "education", "training", "learning", "curriculum", "school", "student",
            "workforce", "implementation", "organizational change", "accessibility",
        ),
        limitations=(
            "methodology analogue only; SARA does not claim a human EdD credential",
            "context-specific educational decisions require evidence and accountable human judgment",
        ),
    ),
    ExpertLens(
        lens_id="ai-research-phd",
        kind=ExpertLensKind.AI_RESEARCH_PHD,
        title="Advanced artificial-intelligence research lens",
        method_steps=(
            "define model, agent, data, tool, memory, and execution boundaries",
            "identify training/inference assumptions and capability limits",
            "evaluate benchmarks, ablations, adversarial tests, and distribution shift",
            "analyze safety, alignment, security, privacy, provenance, and misuse pathways",
            "separate model quality from system reliability and execution authority",
            "require reproducible evidence before claims of autonomy, intelligence, or production readiness",
        ),
        triggers=(
            "ai", "artificial intelligence", "machine learning", "llm", "agent", "model",
            "rag", "neural", "transformer", "inference", "training", "prompt", "mcp",
        ),
        limitations=(
            "research methodology analogue only; SARA is not a human PhD holder",
            "the lens does not establish consciousness, sentience, or autonomous authority",
        ),
    ),
)


INDUSTRY_TRIGGER_MAP: dict[str, tuple[str, ...]] = {
    "healthcare": ("healthcare", "hospital", "patient", "clinical", "medical"),
    "life_sciences": ("pharma", "biotech", "drug", "clinical trial", "life science"),
    "cybersecurity": ("cyber", "security", "soc", "siem", "malware", "zero trust"),
    "software": ("software", "saas", "application", "api", "developer", "cloud"),
    "finance": ("finance", "bank", "banking", "investment", "capital", "fintech"),
    "insurance": ("insurance", "underwriting", "claims", "actuarial"),
    "manufacturing": ("manufacturing", "factory", "industrial", "plant", "production line"),
    "energy": ("energy", "utility", "power grid", "oil", "gas", "renewable"),
    "transportation": ("transportation", "logistics", "fleet", "rail", "shipping"),
    "aerospace": ("aerospace", "aviation", "aircraft", "spacecraft", "satellite"),
    "telecommunications": ("telecom", "telecommunications", "network carrier", "5g", "6g"),
    "retail": ("retail", "commerce", "ecommerce", "merchandising"),
    "supply_chain": ("supply chain", "warehouse", "procurement", "inventory"),
    "government_public_sector": ("government", "public sector", "agency", "municipal"),
    "defense": ("defense", "military", "mission system"),
    "construction": ("construction", "building project", "contractor"),
    "real_estate": ("real estate", "property", "mortgage", "lease"),
    "agriculture": ("agriculture", "farm", "crop", "livestock"),
    "media_entertainment": ("media", "entertainment", "broadcast", "streaming"),
    "hospitality": ("hospitality", "hotel", "restaurant", "tourism"),
    "human_resources": ("human resources", "hr", "recruiting", "workforce"),
    "education": ("education", "school", "university", "training", "curriculum"),
    "legal_services": ("law firm", "legal services", "litigation", "counsel"),
    "research_science": ("research", "laboratory", "scientific", "experiment"),
    "accessibility": ("accessibility", "wcag", "section 508", "assistive technology"),
}


class ExpertReasoningFabric:
    """Governed expert-method synthesis without credential or consciousness claims."""

    def __init__(self) -> None:
        self.core_lenses = {lens.lens_id: lens for lens in CORE_LENSES}

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-expert-reasoning-fabric",
            "available_methodologies": [lens.kind.value for lens in CORE_LENSES],
            "dynamic_industry_lenses": True,
            "claims_human_credentials": False,
            "claims_human_consciousness": False,
            "claims_ai_consciousness": False,
            "execution_authority": False,
            "release_authority": False,
            "boundary": (
                "SARA may apply expert reasoning methodologies but does not impersonate degree holders, "
                "claim consciousness, or treat a simulated lens as evidence."
            ),
        }

    def synthesize(
        self,
        objective: str,
        *,
        evidence: Iterable[dict[str, Any]] | None = None,
        industries: Iterable[str] | str | None = None,
    ) -> dict[str, Any]:
        objective_text = str(objective or "").strip()
        selected = self._select_core_lenses(objective_text)
        industry_names = self._resolve_industries(objective_text, industries)
        industry_lenses = [self._industry_lens(name) for name in industry_names]

        evidence_items = list(evidence or [])
        lenses = [*selected, *industry_lenses]
        return {
            "objective": objective_text,
            "selected_lenses": [lens.as_dict() for lens in lenses],
            "selected_lens_ids": [lens.lens_id for lens in lenses],
            "industry_lenses": industry_names,
            "cross_examination_questions": self._cross_examination_questions(lenses),
            "evidence_count": len(evidence_items),
            "domain_evidence_required": True,
            "human_review_required_when_regulated_or_high_stakes": True,
            "claims_human_credentials": False,
            "claims_human_consciousness": False,
            "claims_ai_consciousness": False,
            "simulated_expert_output_is_not_evidence": True,
            "execution_authority": False,
            "release_authority": False,
        }

    def _select_core_lenses(self, objective: str) -> list[ExpertLens]:
        lower = objective.lower()
        selected: list[ExpertLens] = [self.core_lenses["phd-research"]]
        for lens_id in ("jd-legal", "edd-applied", "ai-research-phd"):
            lens = self.core_lenses[lens_id]
            if any(trigger in lower for trigger in lens.triggers):
                selected.append(lens)
        return selected

    def _resolve_industries(
        self,
        objective: str,
        industries: Iterable[str] | str | None,
    ) -> list[str]:
        requested: list[str] = []
        if isinstance(industries, str):
            requested = [industries]
        elif industries is not None:
            requested = [str(item) for item in industries]

        inferred: list[str] = []
        lower = objective.lower()
        for name, triggers in INDUSTRY_TRIGGER_MAP.items():
            if any(trigger in lower for trigger in triggers):
                inferred.append(name)

        normalized = [self._normalize_industry(item) for item in [*requested, *inferred] if str(item).strip()]
        return list(dict.fromkeys(normalized))

    @staticmethod
    def _normalize_industry(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
        return normalized or "unspecified_industry"

    @staticmethod
    def _industry_lens(industry: str) -> ExpertLens:
        return ExpertLens(
            lens_id=f"industry-{industry}",
            kind=ExpertLensKind.INDUSTRY_DOMAIN,
            title=f"Evidence-bound industry lens: {industry.replace('_', ' ')}",
            method_steps=(
                "define the industry's operational context, stakeholders, assets, and failure modes",
                "identify applicable standards, regulation, economics, safety, and professional practice",
                "separate generic assumptions from industry-specific evidence",
                "map technical decisions to operational and human consequences",
                "identify domain experts, measurements, and external evidence required for validation",
                "state unresolved domain uncertainty before recommendation or execution",
            ),
            limitations=(
                "dynamic industry lens does not claim professional licensure or lived industry experience",
                "industry-specific conclusions require current evidence and accountable domain review where appropriate",
            ),
        )

    @staticmethod
    def _cross_examination_questions(lenses: list[ExpertLens]) -> list[str]:
        questions = [
            "What evidence would falsify the leading conclusion?",
            "Which assumptions are shared across lenses and therefore create correlated error?",
            "What material evidence, jurisdiction, population, or operating context is missing?",
            "Which conclusion changes if the strongest opposing interpretation is correct?",
        ]
        if any(lens.kind == ExpertLensKind.LEGAL_JD for lens in lenses):
            questions.append("What controlling authority or jurisdiction could change the legal analysis?")
        if any(lens.kind == ExpertLensKind.EDUCATION_EDD for lens in lenses):
            questions.append("How will implementation outcomes be measured for the affected learners or organization?")
        if any(lens.kind == ExpertLensKind.AI_RESEARCH_PHD for lens in lenses):
            questions.append("Which benchmark or adversarial test would distinguish model capability from system reliability?")
        if any(lens.kind == ExpertLensKind.INDUSTRY_DOMAIN for lens in lenses):
            questions.append("Which domain-specific standard or practitioner evidence must be verified before action?")
        return questions
