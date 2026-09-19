from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .baez_duarte import (
    finite_range_j_n,
    mobius_sieve,
    psi_n,
    theta_n,
    truncated_j_n,
)


@dataclass(frozen=True)
class TailCertificate:
    n: int
    cutoff: int
    exact_window_n_to_cutoff: float
    remainder_upper_bound: float
    certified_lower_bound: float
    certified_upper_bound: float
    pointwise_residual_bound: float
    normalized_upper_over_log_squared: float
    proof_status: str = "NUMERICAL_EVIDENCE"
    asymptotic_certified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "cutoff": self.cutoff,
            "exact_window_n_to_cutoff": self.exact_window_n_to_cutoff,
            "remainder_upper_bound": self.remainder_upper_bound,
            "certified_lower_bound": self.certified_lower_bound,
            "certified_upper_bound": self.certified_upper_bound,
            "pointwise_residual_bound": self.pointwise_residual_bound,
            "normalized_upper_over_log_squared": self.normalized_upper_over_log_squared,
            "proof_status": self.proof_status,
            "asymptotic_certified": self.asymptotic_certified,
        }


def tail_weights(n: int) -> list[float]:
    """a_{k,N}=mu(k)(log N-log k), one-indexed with a_0=0."""
    if n < 2:
        raise ValueError("tail_weights_requires_n_ge_2")
    mu = mobius_sieve(n)
    log_n = math.log(n)
    return [0.0] + [
        float(mu[k]) * (log_n - math.log(k))
        for k in range(1, n + 1)
    ]


def residual_period(n: int) -> int:
    """A period of R_N(y)=theta_N*y-psi_N(y): lcm(1,...,N)."""
    if n < 2:
        raise ValueError("residual_period_requires_n_ge_2")
    period = 1
    for k in range(1, n + 1):
        period = math.lcm(period, k)
    return period


def pointwise_tail_residual_bound(n: int) -> float:
    """Unconditional fixed-N bound from 0 <= {y/k} < 1.

    |R_N(y)| <= log N + sum_{k<=N}|a_{k,N}|.
    This is intentionally crude and is not an asymptotic RH certificate.
    """
    weights = tail_weights(n)
    return math.log(n) + sum(abs(value) for value in weights[1:])


def period_mean_square(n: int) -> float:
    """Exact mean of R_N(y)^2 over any full residual period.

    With a_k=mu(k)(log N-log k) and B_1({x})={x}-1/2,
    the centered sawtooth covariance is
        mean(B_1(y/m) B_1(y/n)) = gcd(m,n)^2/(12mn)
    over a common period.
    """
    weights = tail_weights(n)
    log_n = math.log(n)
    mean_component = log_n + 0.5 * sum(weights[1:])
    covariance = 0.0
    for m in range(1, n + 1):
        for k in range(1, n + 1):
            covariance += (
                weights[m]
                * weights[k]
                * (math.gcd(m, k) ** 2)
                / (m * k)
            )
    covariance /= 12.0
    value = mean_component * mean_component + covariance
    if -1e-12 < value < 0.0:
        value = 0.0
    return value


def _unweighted_interval_square(theta: float, constant: float, a: float, b: float) -> float:
    """Integral_a^b (theta*y-constant)^2 dy."""
    return (
        (theta * theta / 3.0) * (b**3 - a**3)
        - theta * constant * (b**2 - a**2)
        + constant * constant * (b - a)
    )


def direct_period_mean_square(n: int, *, max_period: int = 200_000) -> float:
    """Direct exact-by-unit-interval validation of the period mean square.

    This is a validation helper for modest N only; it refuses enormous lcm periods.
    """
    period = residual_period(n)
    if period > max_period:
        raise ValueError("period_too_large_for_direct_validation")
    theta = theta_n(n)
    start = period
    total = 0.0
    for m in range(start, start + period):
        constant = psi_n(float(m), n)
        total += _unweighted_interval_square(theta, constant, float(m), float(m + 1))
    return total / period


def certified_tail_interval(n: int, cutoff: int) -> TailCertificate:
    """Certified fixed-N interval for T_N=int_N^inf R_N(y)^2 dy/y^2.

    The window [N,cutoff] is integrated exactly by the existing unit-interval
    engine. The uncomputed remainder is bounded by B_N^2/cutoff using the
    unconditional pointwise bound |R_N(y)| <= B_N.

    This proves a finite-N enclosure only. It does not establish
    T_N=o(log^2 N), J_N=o(log^2 N), or RH.
    """
    if n < 2 or cutoff <= n:
        raise ValueError("certified_tail_requires_cutoff_gt_n_ge_2")
    exact_window = truncated_j_n(n, cutoff) - finite_range_j_n(n)
    bound = pointwise_tail_residual_bound(n)
    remainder = (bound * bound) / cutoff
    upper = exact_window + remainder
    log_squared = math.log(n) ** 2
    return TailCertificate(
        n=n,
        cutoff=cutoff,
        exact_window_n_to_cutoff=exact_window,
        remainder_upper_bound=remainder,
        certified_lower_bound=exact_window,
        certified_upper_bound=upper,
        pointwise_residual_bound=bound,
        normalized_upper_over_log_squared=upper / log_squared,
    )


def tail_attack_snapshot(n: int = 8, cutoff: int = 128) -> dict[str, Any]:
    """Research snapshot for Tail Attack I with explicit proof boundary."""
    certificate = certified_tail_interval(n, cutoff)
    period = residual_period(n)
    return {
        "phase": "TAIL_ATTACK_I",
        "n": n,
        "cutoff": cutoff,
        "residual_period_lcm_1_to_n": period,
        "period_mean_square": period_mean_square(n),
        "certificate": certificate.as_dict(),
        "identities": {
            "periodicity": "R_N(y+L_N)=R_N(y), L_N=lcm(1,...,N)",
            "period_mean_square": (
                "M_N=(log N + 1/2 sum a_n)^2 + "
                "(1/12) sum_{m,n} a_m a_n gcd(m,n)^2/(mn)"
            ),
            "fixed_n_remainder_bound": "int_C^inf R_N(y)^2/y^2 dy <= B_N^2/C",
        },
        "proof_status": "NUMERICAL_EVIDENCE",
        "asymptotic_target": "tail_N=o(log^2 N)",
        "asymptotic_certified": False,
        "limitations": [
            "The lcm period grows rapidly with N.",
            "A fixed-N certified enclosure does not prove a uniform N-to-infinity estimate.",
            "The crude pointwise remainder bound may be far too large for the RH target.",
            "Period mean-square cancellation alone does not control the tail beginning at y=N.",
        ],
    }
