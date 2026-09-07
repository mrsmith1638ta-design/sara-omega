from __future__ import annotations

from .models import (
    ApplicabilityScope,
    CertaintyLevel,
    ProvenanceClass,
    ScienceAnalysis,
    ScienceClaim,
    TruthGateDecision,
    UniversalityStatus,
)


_CERTAINTY_RANK = {
    CertaintyLevel.UNKNOWN: 0,
    CertaintyLevel.UNVERIFIED: 1,
    CertaintyLevel.DISPUTED: 2,
    CertaintyLevel.INFERRED: 3,
    CertaintyLevel.SUPPORTED: 4,
    CertaintyLevel.VERIFIED: 5,
}

_NON_UNIVERSAL_SCOPES = {
    ApplicabilityScope.FAMILY_LEVEL,
    ApplicabilityScope.ARCHITECTURE_SPECIFIC,
    ApplicabilityScope.CONFIGURATION_SPECIFIC,
    ApplicabilityScope.EXPERIMENTAL_OBSERVATION,
    ApplicabilityScope.HISTORICAL_RECONSTRUCTION,
    ApplicabilityScope.UNKNOWN,
}

_UNIVERSALIZING_MARKERS = (
    " all ",
    " every ",
    " never ",
    " always ",
    " requires no ",
    " proves ",
)

_SCOPE_BY_PROVENANCE = {
    ProvenanceClass.DOCUMENTED_ANCIENT: ApplicabilityScope.HISTORICAL_DOCUMENTATION,
    ProvenanceClass.HISTORICALLY_COMPATIBLE_RECONSTRUCTION: ApplicabilityScope.HISTORICAL_RECONSTRUCTION,
    ProvenanceClass.MODERN_ENGINEERING_DERIVATION: ApplicabilityScope.CONFIGURATION_SPECIFIC,
    ProvenanceClass.ESTABLISHED_PHYSICS: ApplicabilityScope.UNIVERSAL_LAW,
    ProvenanceClass.DOCUMENTED_TECHNOLOGY: ApplicabilityScope.ARCHITECTURE_SPECIFIC,
    ProvenanceClass.ENGINEERING_MODEL: ApplicabilityScope.ARCHITECTURE_SPECIFIC,
    ProvenanceClass.EXPERIMENTAL_TECHNOLOGY: ApplicabilityScope.EXPERIMENTAL_OBSERVATION,
    ProvenanceClass.SIMULATION_OR_HYPOTHESIS: ApplicabilityScope.CONFIGURATION_SPECIFIC,
}

_CEILING_BY_PROVENANCE = {
    ProvenanceClass.DOCUMENTED_ANCIENT: CertaintyLevel.SUPPORTED,
    ProvenanceClass.HISTORICALLY_COMPATIBLE_RECONSTRUCTION: CertaintyLevel.INFERRED,
    ProvenanceClass.MODERN_ENGINEERING_DERIVATION: CertaintyLevel.SUPPORTED,
    ProvenanceClass.ESTABLISHED_PHYSICS: CertaintyLevel.VERIFIED,
    ProvenanceClass.DOCUMENTED_TECHNOLOGY: CertaintyLevel.SUPPORTED,
    ProvenanceClass.ENGINEERING_MODEL: CertaintyLevel.INFERRED,
    ProvenanceClass.EXPERIMENTAL_TECHNOLOGY: CertaintyLevel.SUPPORTED,
    ProvenanceClass.SIMULATION_OR_HYPOTHESIS: CertaintyLevel.INFERRED,
}


class HighLevelTruthGate:
    """Deterministic fail-closed certainty and applicability gate."""

    def evaluate_claim(self, claim: ScienceClaim) -> TruthGateDecision:
        gated = claim.certainty_level
        universality = claim.universality_status
        reasons: list[str] = []

        if _CERTAINTY_RANK[gated] > _CERTAINTY_RANK[claim.certainty_ceiling]:
            gated = claim.certainty_ceiling
            reasons.append("certainty capped by claim ceiling")

        if claim.applicability_scope in _NON_UNIVERSAL_SCOPES and universality == UniversalityStatus.UNIVERSAL_SUPPORTED:
            universality = UniversalityStatus.SYSTEM_DEPENDENT
            reasons.append("non-universal applicability scope cannot support universal wording")

        if not claim.source_ids:
            universality = UniversalityStatus.INSUFFICIENT_EVIDENCE
            gated = self._downgrade_at_most(gated, CertaintyLevel.UNVERIFIED)
            reasons.append("no supporting source identifiers")

        if claim.evidence_status.upper() in {"STALE", "UNVERIFIED", "UNKNOWN", "CURRENTLY_UNVERIFIED"}:
            universality = UniversalityStatus.INSUFFICIENT_EVIDENCE
            gated = self._downgrade_at_most(gated, CertaintyLevel.UNVERIFIED)
            reasons.append("evidence status does not support current factual certainty")

        if claim.applicability_scope in _NON_UNIVERSAL_SCOPES and not claim.dependency_conditions:
            universality = UniversalityStatus.INSUFFICIENT_EVIDENCE
            gated = self._downgrade_at_most(gated, CertaintyLevel.UNVERIFIED)
            reasons.append("required applicability dependencies are missing")

        if any("illustrative default" in item.lower() for item in claim.assumptions):
            gated = self._downgrade_at_most(gated, CertaintyLevel.INFERRED)
            reasons.append("illustrative defaults cannot be presented as user-specific facts")

        disposition = "ACCEPTED"
        if reasons:
            disposition = "QUALIFIED"
        if universality == UniversalityStatus.INSUFFICIENT_EVIDENCE and gated == CertaintyLevel.UNKNOWN:
            disposition = "REJECTED"

        return TruthGateDecision(
            claim_text=claim.claim_text,
            original_certainty=claim.certainty_level,
            gated_certainty=gated,
            universality_status=universality,
            disposition=disposition,
            reasons=reasons,
            applicability_scope=claim.applicability_scope,
            provenance_class=claim.provenance_class,
            source_ids=list(claim.source_ids),
        )

    def gate_analysis(self, analysis: ScienceAnalysis) -> dict[str, list[dict[str, object]]]:
        claims: list[ScienceClaim] = []
        decisions: list[TruthGateDecision] = []
        for calculation in analysis.calculations:
            scope = _SCOPE_BY_PROVENANCE[calculation.provenance_class]
            ceiling = _CEILING_BY_PROVENANCE[calculation.provenance_class]
            result = calculation.result if isinstance(calculation.result, dict) else {}
            dependencies = [str(item) for item in result.get("dependencies", []) if str(item).strip()]
            if not dependencies and scope == ApplicabilityScope.UNIVERSAL_LAW:
                dependencies = ["law applicability assumptions"]
            certainty = CertaintyLevel.SUPPORTED if calculation.evidence_status.upper() == "SUPPORTED" else CertaintyLevel.UNVERIFIED
            universality = (
                UniversalityStatus.UNIVERSAL_SUPPORTED
                if scope == ApplicabilityScope.UNIVERSAL_LAW
                else UniversalityStatus.SYSTEM_DEPENDENT
            )
            claim = ScienceClaim(
                claim_text=f"{analysis.domain}:{calculation.equation_id}",
                provenance_class=calculation.provenance_class,
                evidence_status=calculation.evidence_status,
                applicability_scope=scope,
                certainty_level=certainty,
                dependency_conditions=dependencies,
                source_ids=list(calculation.source_ids),
                assumptions=list(calculation.assumptions),
                limitations=list(calculation.limitations),
                validation_status=calculation.validation_status,
                universality_status=universality,
                certainty_ceiling=ceiling,
            )
            claims.append(claim)
            decisions.append(self.evaluate_claim(claim))
        return {
            "claims": [item.model_dump(mode="json") for item in claims],
            "decisions": [item.model_dump(mode="json") for item in decisions],
        }

    def evaluate_final_synthesis(self, text: str, claims: list[ScienceClaim]) -> dict[str, object]:
        normalized = f" {text.strip().lower()} "
        has_system_dependent_claim = any(
            self.evaluate_claim(claim).universality_status
            in {UniversalityStatus.SYSTEM_DEPENDENT, UniversalityStatus.INSUFFICIENT_EVIDENCE}
            for claim in claims
        )
        overstates = has_system_dependent_claim and any(marker in normalized for marker in _UNIVERSALIZING_MARKERS)
        if overstates:
            return {
                "allowed": False,
                "status": UniversalityStatus.SYSTEM_DEPENDENT.value,
                "reason": "candidate synthesis promotes a scoped claim to universal wording",
            }
        return {"allowed": True, "status": "PASS", "reason": None}

    def evaluate_text_claim(self, text: str) -> dict[str, object]:
        normalized = f" {text.strip().lower()} "
        universalized = any(marker in normalized for marker in _UNIVERSALIZING_MARKERS)
        historical_overclaim = "great pyramid" in normalized and any(
            token in normalized for token in ("electromagnetic technology", "modern technology", "proves")
        )
        if historical_overclaim:
            status = "INSUFFICIENT_EVIDENCE"
        elif universalized:
            status = "SYSTEM_DEPENDENT"
        else:
            status = "UNVERIFIED"
        return {
            "status": status,
            "allowed_as_unqualified_fact": False,
        }

    @staticmethod
    def _downgrade_at_most(current: CertaintyLevel, ceiling: CertaintyLevel) -> CertaintyLevel:
        if _CERTAINTY_RANK[current] > _CERTAINTY_RANK[ceiling]:
            return ceiling
        return current
