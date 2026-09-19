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

    def evaluate_tail_attack_ii_uniform_claim(
        self,
        claim: str,
        *,
        proof_status: RHProofStatus,
        covariance_uniform_bound_proved: bool = False,
        mean_component_uniform_bound_proved: bool = False,
        cumulative_energy_discrepancy_proved: bool = False,
        period_to_tail_transfer_proved: bool = False,
        assumes_rh: bool = False,
        assumes_mobius_randomness: bool = False,
        formal_certificate: str | None = None,
    ) -> RHGateDecision:
        """Fail-closed gate for the Tail Attack II covariance route.

        This gate is route-specific. It prevents the proved covariance estimate
        C_N=O(N) from being silently promoted into a theorem about the weighted
        tail T_N without the remaining uniform estimates.
        """
        text = claim.strip().lower()
        reasons: list[str] = []

        if assumes_rh:
            reasons.append("Tail Attack II uniform bound cannot assume RH or an RH-equivalent statement")
        if assumes_mobius_randomness:
            reasons.append("Tail Attack II uniform bound cannot assume unproved Mobius randomness or square-root cancellation")
        if proof_status == RHProofStatus.NUMERICAL_EVIDENCE:
            reasons.append("finite numerical covariance data cannot certify a uniform N-to-infinity tail bound")
        if not covariance_uniform_bound_proved:
            reasons.append("the covariance route requires a proved uniform covariance estimate")
        if not mean_component_uniform_bound_proved:
            reasons.append("period mean-square control still requires a proved uniform mean-component estimate")
        if not cumulative_energy_discrepancy_proved:
            reasons.append("period statistics do not control the weighted tail without a proved cumulative-energy discrepancy estimate")
        if not period_to_tail_transfer_proved:
            reasons.append("a valid period-to-tail transfer must be proved before promoting covariance control to T_N")
        if "covariance" in text and "therefore" in text and "tail" in text:
            if not cumulative_energy_discrepancy_proved or not period_to_tail_transfer_proved:
                reasons.append("covariance control alone does not imply the weighted tail asymptotic")
        if proof_status == RHProofStatus.FORMAL_PROOF_CERTIFIED and not formal_certificate:
            reasons.append("formal Tail Attack II status requires a certificate reference")

        if reasons:
            return RHGateDecision(False, "BLOCK", list(dict.fromkeys(reasons)))
        return RHGateDecision(True, "PASS", [])

    def evaluate_tail_attack_iii_claim(
        self,
        claim: str,
        *,
        proof_status: RHProofStatus,
        covariance_bound_proved: bool = True,
        mean_component_bound_proved: bool = False,
        discrepancy_bound_proved: bool = False,
        weighted_transfer_proved: bool = True,
        assumes_rh: bool = False,
        assumes_mobius_randomness: bool = False,
        assumes_unproved_pnt_strength: bool = False,
        finite_period_only: bool = False,
        formal_certificate: str | None = None,
    ) -> RHGateDecision:
        """Fail-closed gate for mean-component plus weighted-tail transfer claims."""
        text = claim.strip().lower()
        reasons: list[str] = []

        if assumes_rh:
            reasons.append("Tail Attack III cannot assume RH or an RH-equivalent statement")
        if assumes_mobius_randomness:
            reasons.append("Tail Attack III cannot assume unproved Mobius randomness or square-root cancellation")
        if assumes_unproved_pnt_strength:
            reasons.append("Tail Attack III cannot smuggle in an unproved PNT-strength cancellation estimate")
        if not covariance_bound_proved:
            reasons.append("Tail Attack III requires the Tail Attack II covariance bound")
        if not weighted_transfer_proved:
            reasons.append("period energy cannot be identified with the weighted tail without a proved transfer identity")
        if finite_period_only and not discrepancy_bound_proved:
            reasons.append("a finite-period average cannot certify the weighted tail without an explicit transfer-discrepancy bound")
        if not mean_component_bound_proved:
            reasons.append("the mean-component target A_N^2/N=o(log^2 N) remains unproved")
        if not discrepancy_bound_proved:
            reasons.append("the discrepancy target D_N/N^2=o(log^2 N) remains unproved")
        if proof_status == RHProofStatus.NUMERICAL_EVIDENCE:
            reasons.append("finite numerical Tail Attack III data cannot certify an N-to-infinity little-o theorem")

        hidden_shortcuts = (
            "mobius is random",
            "möbius is random",
            "random signs",
            "square-root cancellation",
            "sqrt cancellation",
            "finite period therefore",
            "period average equals tail",
            "assume prime number theorem error",
            "assuming rh",
        )
        if any(marker in text for marker in hidden_shortcuts):
            reasons.append("claim contains a prohibited hidden cancellation or period-to-tail shortcut")

        if proof_status == RHProofStatus.FORMAL_PROOF_CERTIFIED and not formal_certificate:
            reasons.append("formal Tail Attack III status requires a certificate reference")

        if reasons:
            return RHGateDecision(False, "BLOCK", list(dict.fromkeys(reasons)))
        return RHGateDecision(True, "PASS", [])

    def evaluate_tail_attack_iv_claim(
        self,
        claim: str,
        *,
        proof_status: RHProofStatus,
        mean_bound_sourced: bool = False,
        mean_target_proved: bool = False,
        covariance_target_proved: bool = True,
        discrepancy_target_proved: bool = False,
        combined_tail_claim: bool = False,
        assumes_rh: bool = False,
        assumes_mobius_randomness: bool = False,
        uses_unsourced_pnt_or_zero_free_bound: bool = False,
        finite_period_or_subperiod_only: bool = False,
        formal_certificate: str | None = None,
    ) -> RHGateDecision:
        """Fail-closed gate for Tail Attack IV dependency-graph promotion."""
        text = claim.strip().lower()
        reasons: list[str] = []

        if assumes_rh:
            reasons.append("Tail Attack IV cannot assume RH or a zeta-zero-location equivalent")
        if assumes_mobius_randomness:
            reasons.append("Tail Attack IV cannot assume Mobius randomness or square-root cancellation")
        if uses_unsourced_pnt_or_zero_free_bound or not mean_bound_sourced:
            reasons.append("mean-component claims require an explicit source for imported Mertens/PNT bounds")
        if not mean_target_proved:
            reasons.append("the mean dependency A_N^2/N=o(log^2 N) remains unproved")
        if not covariance_target_proved:
            reasons.append("the covariance dependency C_N=O(N) must remain proved and attached")
        if finite_period_or_subperiod_only and not discrepancy_target_proved:
            reasons.append("finite period/subperiod balancing cannot certify the uniform D_N rate")
        if not discrepancy_target_proved:
            reasons.append("the discrepancy dependency D_N/N^2=o(log^2 N) remains unproved")
        if combined_tail_claim and (not mean_target_proved or not covariance_target_proved or not discrepancy_target_proved):
            reasons.append("combined weighted-tail promotion requires every dependency to be proved")
        if proof_status == RHProofStatus.NUMERICAL_EVIDENCE and combined_tail_claim:
            reasons.append("finite numerical dashboard values cannot certify the asymptotic tail theorem")

        prohibited_markers = (
            "mobius is random",
            "möbius is random",
            "square-root cancellation",
            "sqrt cancellation",
            "period average therefore",
            "subperiods prove",
            "assuming rh",
            "all zeros lie on",
        )
        if any(marker in text for marker in prohibited_markers):
            reasons.append("claim contains a prohibited cancellation, zero-location, or finite-period shortcut")

        if proof_status == RHProofStatus.FORMAL_PROOF_CERTIFIED and not formal_certificate:
            reasons.append("formal Tail Attack IV status requires a certificate reference")

        if reasons:
            return RHGateDecision(False, "BLOCK", list(dict.fromkeys(reasons)))
        return RHGateDecision(True, "PASS", [])

    def evaluate_tail_attack_v_claim(
        self,
        claim: str,
        *,
        proof_status: RHProofStatus,
        mean_obstruction_resolved: bool = False,
        discrepancy_growth_proved: bool = False,
        covariance_bound_proved: bool = True,
        combined_tail_claim: bool = False,
        uses_zero_structure_shortcut: bool = False,
        assumes_rh: bool = False,
        assumes_mobius_randomness: bool = False,
        finite_discrepancy_only: bool = False,
        formal_certificate: str | None = None,
    ) -> RHGateDecision:
        """Fail-closed gate for Tail Attack V mean-obstruction promotion."""
        text = claim.strip().lower()
        reasons: list[str] = []

        if assumes_rh:
            reasons.append("Tail Attack V cannot assume RH while auditing an RH-sensitive obstruction")
        if assumes_mobius_randomness:
            reasons.append("Tail Attack V cannot assume Mobius randomness or square-root cancellation")
        if uses_zero_structure_shortcut:
            reasons.append("zero-structure shortcuts require a proof-grade certificate, not a heuristic")
        if not mean_obstruction_resolved:
            reasons.append("the mean obstruction A_N=o(sqrt(N) log N) remains unresolved")
        if not discrepancy_growth_proved:
            reasons.append("the discrepancy growth theorem D_N/N^2=o(log^2 N) remains unproved")
        if not covariance_bound_proved:
            reasons.append("Tail Attack V still depends on the Tail Attack II covariance theorem")
        if finite_discrepancy_only and not discrepancy_growth_proved:
            reasons.append("finite discrepancy diagnostics cannot certify a uniform discrepancy theorem")
        if combined_tail_claim and (
            not mean_obstruction_resolved
            or not discrepancy_growth_proved
            or not covariance_bound_proved
        ):
            reasons.append("combined Tail Attack V promotion requires mean, covariance, and discrepancy dependencies to be proved")
        if proof_status == RHProofStatus.NUMERICAL_EVIDENCE and combined_tail_claim:
            reasons.append("finite Tail Attack V diagnostics cannot certify the asymptotic tail theorem")

        prohibited_markers = (
            "mobius is random",
            "möbius is random",
            "square-root cancellation",
            "sqrt cancellation",
            "near-square-root follows",
            "zeta zero structure",
            "assuming rh",
            "therefore rh",
            "rh follows",
        )
        if any(marker in text for marker in prohibited_markers):
            reasons.append("claim contains a prohibited mean-obstruction or proof-promotion shortcut")

        if proof_status == RHProofStatus.FORMAL_PROOF_CERTIFIED and not formal_certificate:
            reasons.append("formal Tail Attack V status requires a certificate reference")

        if reasons:
            return RHGateDecision(False, "BLOCK", list(dict.fromkeys(reasons)))
        return RHGateDecision(True, "PASS", [])

