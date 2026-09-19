from __future__ import annotations

import re

from .models import RiemannProofStatus, RiemannResult


class RiemannProofGate:
    def evaluate(self, text: str, result: RiemannResult | None = None) -> dict[str, object]:
        normalized = f" {text.lower()} "
        reasons: list[str] = []

        proof_language = any(token in normalized for token in (" proved", " proof", " solved", "qed", "certified"))
        rh_context = any(
            token in normalized
            for token in ("riemann hypothesis", " rh ", " zeta", "vasyunin", "baez-duarte", "nyman", "mellin")
        )
        finite_marker = bool(re.search(r"n\s*(<=|<|=)|tested|finite|scan|numerical|observed", normalized))
        circular_marker = any(
            token in normalized
            for token in ("assume rh", "assuming rh", "assume the riemann hypothesis", "all zeros lie on", "zero-free line")
        )
        quantum_marker = any(token in normalized for token in ("quantum", "hamiltonian", "spectrum", "spectral"))

        if circular_marker:
            reasons.append("circular RH or RH-equivalent assumption detected")
        if proof_language and rh_context and finite_marker:
            reasons.append("finite numerical evidence cannot prove an infinite RH limit")
        if proof_language and rh_context and quantum_marker:
            reasons.append("quantum or spectral interpretation cannot certify RH")
        if result and result.status != RiemannProofStatus.FORMAL_PROOF_CERTIFIED and proof_language:
            reasons.append(f"{result.status.value} cannot support proof language")
        if result and result.status == RiemannProofStatus.FORMAL_PROOF_CERTIFIED and not result.certificate_id:
            reasons.append("formal proof status requires a proof certificate")

        allowed = not reasons and bool(result and result.status == RiemannProofStatus.FORMAL_PROOF_CERTIFIED)
        return {
            "allowed_as_proof": allowed,
            "status": "PASS" if allowed else "REJECTED_OR_QUALIFIED",
            "reasons": reasons or ["no formal proof certificate supplied"],
        }

