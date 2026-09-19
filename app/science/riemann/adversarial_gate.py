from __future__ import annotations

from dataclasses import dataclass, field

from .models import RHProofStatus


_PROOF_LANGUAGE = (
    "rh proved",
    "riemann hypothesis proved",
    "proves the riemann hypothesis",
    "proof of the riemann hypothesis",
    "therefore rh is true",
    "therefore the riemann hypothesis is true",
)


@dataclass(frozen=True)
class RHGateDecision:
    allowed: bool
    status: str
    reasons: list[str] = field(default_factory=list)


class RHAdversarialGate:
    """Fail-closed proof-promotion gate for the RH research engine."""

    def evaluate(
        self,
        *,
        claim: str,
        proof_status: RHProofStatus,
        formal_certificate: str | None = None,
        infinite_limit_proved: bool = False,
        assumes_rh: bool = False,
        finite_n_only: bool = False,
        spectral_or_quantum_only: bool = False,
    ) -> RHGateDecision:
        text = claim.strip().lower()
        attempts_proof_promotion = any(marker in text for marker in _PROOF_LANGUAGE)
        reasons: list[str] = []

        if assumes_rh and attempts_proof_promotion:
            reasons.append("circular reasoning: RH is assumed in a claimed RH proof")
        if finite_n_only and attempts_proof_promotion:
            reasons.append("finite-N evidence cannot establish the N-to-infinity limit")
        if spectral_or_quantum_only and attempts_proof_promotion:
            reasons.append("spectral/quantum evidence alone cannot certify an infinite theorem")
        if proof_status == RHProofStatus.NUMERICAL_EVIDENCE and attempts_proof_promotion:
            reasons.append("numerical evidence cannot be promoted to theorem")
        if proof_status == RHProofStatus.CONJECTURAL_LEMMA and attempts_proof_promotion:
            reasons.append("an unproved lemma cannot certify RH")
        if proof_status == RHProofStatus.SYMBOLIC_IDENTITY and attempts_proof_promotion:
            reasons.append("a symbolic identity is not by itself a proof of the required limit")
        if proof_status == RHProofStatus.FORMAL_PROOF_CERTIFIED:
            if not formal_certificate:
                reasons.append("formal proof status requires a non-empty certificate reference")
            if not infinite_limit_proved:
                reasons.append("formal RH certification requires the infinite limiting implication")

        if reasons:
            return RHGateDecision(False, "BLOCK", reasons)
        return RHGateDecision(True, "PASS", [])

    def certify_status(
        self,
        proof_status: RHProofStatus,
        *,
        formal_certificate: str | None = None,
        infinite_limit_proved: bool = False,
    ) -> RHGateDecision:
        if proof_status != RHProofStatus.FORMAL_PROOF_CERTIFIED:
            return RHGateDecision(True, "PASS", [])
        return self.evaluate(
            claim="formal proof candidate",
            proof_status=proof_status,
            formal_certificate=formal_certificate,
            infinite_limit_proved=infinite_limit_proved,
        )

    def evaluate_tail_bound_claim(
        self,
        claim: str,
        *,
        proof_status: RHProofStatus,
        formal_certificate: str | None = None,
    ) -> RHGateDecision:
        text = claim.strip().lower()
        reasons: list[str] = []

        hidden_rh_markers = (
            "assume rh",
            "assuming rh",
            "riemann hypothesis is true",
            "all zeta zeros",
            "all zeros lie",
            "critical line",
        )
        strong_unproved_markers = (
            "square-root cancellation",
            "sqrt cancellation",
            "lindelof",
            "lindelöf",
            "mobius randomness",
            "random signs",
            "uncorrelated fractional parts",
        )
        theorem_markers = ("therefore rh", "rh proved", "proves rh", "proves the riemann hypothesis")

        if any(marker in text for marker in hidden_rh_markers):
            reasons.append("hidden RH or zeta-zero assumption cannot support a tail bound")
        if any(marker in text for marker in strong_unproved_markers) and proof_status != RHProofStatus.FORMAL_PROOF_CERTIFIED:
            reasons.append("unproved cancellation hypothesis cannot be promoted to a tail theorem")
        if any(marker in text for marker in theorem_markers) and proof_status != RHProofStatus.FORMAL_PROOF_CERTIFIED:
            reasons.append("tail-bound claim cannot certify RH without formal proof status")
        if proof_status == RHProofStatus.FORMAL_PROOF_CERTIFIED and not formal_certificate:
            reasons.append("formal tail-bound status requires a certificate reference")

        if reasons:
            return RHGateDecision(False, "BLOCK", reasons)
        return RHGateDecision(True, "PASS", [])
