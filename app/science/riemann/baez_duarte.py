from __future__ import annotations

from .models import RiemannProofStatus, RiemannResult, RiemannRoute


def riemann_sufficient_target() -> RiemannRoute:
    return RiemannRoute(
        statement=(
            "theta_N = O(1) and J_N = o(log^2 N) would force ||e_N||_2 -> 0 "
            "and hence RH through the Baez-Duarte/Nyman-Beurling criterion."
        ),
        status=RiemannProofStatus.CANDIDATE_LEMMA,
        evidence=["Baez-Duarte/Nyman-Beurling equivalence route", "SARA V3.4.0 RH engine spec"],
        limitations=["This is an RH-equivalent proof target, not an unconditional proof."],
    )


def error_norm_identity_record(N: int) -> RiemannResult:
    return RiemannResult(
        statement=(
            f"For N={N}, the tracked symbolic form is ||e_N||_2^2 = "
            "theta_N^2 / log^2(N) + J_N / log^2(N)."
        ),
        status=RiemannProofStatus.SYMBOLIC_IDENTITY,
        evidence=["Selberg coefficient transform identity"],
        limitations=["The identity does not prove that J_N = o(log^2 N)."],
        metadata={"N": N},
    )


def split_J_target(N: int) -> RiemannResult:
    return RiemannResult(
        statement=(
            f"J_N for N={N} is split into a finite range 1 <= y <= N and a tail y > N; "
            "the finite range uses psi_N(y)=psi(y), while the tail remains separately bounded."
        ),
        status=RiemannProofStatus.SYMBOLIC_IDENTITY,
        evidence=["Classical divisor identities for y <= N"],
        limitations=["No unconditional asymptotic tail bound is certified by this record."],
        metadata={"N": N, "split": ["finite", "tail"]},
    )

