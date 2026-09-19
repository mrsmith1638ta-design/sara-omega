from __future__ import annotations

from app.science.models import ProvenanceClass, ScienceAnalysis, ScienceCalculation

from .baez_duarte import error_norm_identity_record, riemann_sufficient_target, split_J_target
from .models import RiemannProofStatus
from .proof_gate import RiemannProofGate


class RiemannResearchEngine:
    domain = "riemann_hypothesis"

    def analyze_text(self, text: str) -> ScienceAnalysis:
        route = riemann_sufficient_target()
        identity = error_norm_identity_record(20)
        split = split_J_target(20)
        proof_gate = RiemannProofGate().evaluate(text, route)
        calculations = [
            ScienceCalculation(
                equation_id="riemann.baez_duarte_distance",
                variables={"d_N": "finite reciprocal approximation distance"},
                units={},
                inputs={"reference_N": 20},
                result={"proof_status": route.status.value, "statement": route.statement},
                provenance_class=ProvenanceClass.MODERN_ENGINEERING_DERIVATION,
                evidence_status="UNVERIFIED",
                assumptions=["Baez-Duarte/Nyman-Beurling framework is being used as a research route"],
                limitations=list(route.limitations),
                source_ids=["riemann.local.v340_spec"],
                validation_status="RESEARCH_ROUTE_ONLY",
            ),
            ScienceCalculation(
                equation_id="riemann.J_N_bottleneck",
                variables={"theta_N": "Selberg coefficient normalization", "J_N": "weighted psi_N residual integral"},
                units={},
                inputs={"reference_N": 20},
                result={"identity": identity.statement, "split": split.statement},
                provenance_class=ProvenanceClass.MODERN_ENGINEERING_DERIVATION,
                evidence_status="UNVERIFIED",
                assumptions=["Unconditional J_N=o(log^2 N) is not certified"],
                limitations=["Candidate proof target only; not a proof of RH"],
                source_ids=["riemann.local.v340_spec"],
                validation_status="SYMBOLIC_RESEARCH_RECORD",
            ),
        ]
        return ScienceAnalysis(
            domain=self.domain,
            summary="Riemann Hypothesis research analysis with proof-status gating.",
            calculations=calculations,
            evidence_gaps=["Unconditional proof of theta_N=O(1) and J_N=o(log^2 N)", *proof_gate["reasons"]],
            confidence=0.25,
            execution_authority=False,
            metadata={
                "proof_status": RiemannProofStatus.CANDIDATE_LEMMA.value,
                "riemann_proof_gate": proof_gate,
                "route": route.model_dump(mode="json"),
                "identity": identity.model_dump(mode="json"),
                "split": split.model_dump(mode="json"),
            },
        )

