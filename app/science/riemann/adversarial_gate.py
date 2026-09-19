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
        claims_asymptotic_limit: bool = False,
        uniform_asymptotic_proved: bool = False,
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
        if claims_asymptotic_limit:
            if finite_n_only:
                reasons.append("finite-N tail certification cannot establish a uniform N-to-infinity asymptotic")
            if proof_status == RHProofStatus.NUMERICAL_EVIDENCE:
                reasons.append("numerical tail evidence cannot certify an asymptotic little-o statement")
            if not uniform_asymptotic_proved:
                reasons.append("asymptotic promotion requires a proved uniform N-to-infinity estimate")
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
