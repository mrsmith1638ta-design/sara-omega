from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .baez_duarte import mobius_sieve, psi_n, theta_n, truncated_j_n, finite_range_j_n
from .gcd_covariance import gcd_covariance_jordan
from .tail_attack import (
    certified_tail_interval,
    period_mean_square,
    residual_period,
    tail_weights,
)


@dataclass(frozen=True)
class TailAttackIIICertificate:
    n: int
    period: int
    mean_component: float
    mean_component_squared: float
    covariance_component: float
    period_energy_mean: float
    discrepancy_supremum: float
    discrepancy_endpoint_error: float
    transfer_lower_bound: float
    transfer_upper_bound: float
    normalized_mean_term: float
    normalized_discrepancy_term: float
    proof_status: str = "SYMBOLIC_IDENTITY"
    uniform_tail_certified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "period": self.period,
            "mean_component": self.mean_component,
            "mean_component_squared": self.mean_component_squared,
            "covariance_component": self.covariance_component,
            "period_energy_mean": self.period_energy_mean,
            "discrepancy_supremum": self.discrepancy_supremum,
            "discrepancy_endpoint_error": self.discrepancy_endpoint_error,
            "transfer_lower_bound": self.transfer_lower_bound,
            "transfer_upper_bound": self.transfer_upper_bound,
            "normalized_mean_term": self.normalized_mean_term,
            "normalized_discrepancy_term": self.normalized_discrepancy_term,
            "proof_status": self.proof_status,
            "uniform_tail_certified": self.uniform_tail_certified,
        }


def mean_component(n: int) -> float:
    """A_N = log N + (1/2) sum_{k<=N} mu(k)(log N-log k)."""
    if n < 2:
        raise ValueError("mean_component_requires_n_ge_2")
    weights = tail_weights(n)
    return math.log(n) + 0.5 * sum(weights[1:])


def centered_sawtooth(n: int, y: float) -> float:
    """Centered residual S_N(y)=sum a_k({y/k}-1/2)."""
    if n < 2 or y < 1.0:
        raise ValueError("centered_sawtooth_requires_n_ge_2_and_y_ge_1")
    weights = tail_weights(n)
    return sum(
        weights[k] * (((y / k) - math.floor(y / k)) - 0.5)
        for k in range(1, n + 1)
    )


def centered_residual_identity(n: int, y: float) -> dict[str, float]:
    """Verify R_N(y)=A_N+S_N(y) against theta_N*y-psi_N(y)."""
    if y < 1.0:
        raise ValueError("centered_residual_identity_requires_y_ge_1")
    direct = theta_n(n) * y - psi_n(y, n)
    decomposed = mean_component(n) + centered_sawtooth(n, y)
    return {
        "direct": direct,
        "decomposed": decomposed,
        "absolute_error": abs(direct - decomposed),
    }


def mertens_table(n: int) -> list[int]:
    """M(k)=sum_{m<=k} mu(m), returned for 0<=k<=n."""
    if n < 1:
        raise ValueError("mertens_table_requires_positive_n")
    mu = mobius_sieve(n)
    result = [0] * (n + 1)
    running = 0
    for k in range(1, n + 1):
        running += mu[k]
        result[k] = running
    return result


def mean_component_mertens_form(n: int) -> float:
    """Exact discrete form of A_N=log N+(1/2) integral_1^N M(t)dt/t."""
    if n < 2:
        raise ValueError("mean_component_requires_n_ge_2")
    mertens = mertens_table(n)
    integral = sum(
        mertens[k] * math.log((k + 1) / k)
        for k in range(1, n)
    )
    return math.log(n) + 0.5 * integral


def elementary_mean_component_bound(n: int) -> float:
    """Unconditional baseline from |M(t)|<=t: |A_N|<=log N+(N-1)/2."""
    if n < 2:
        raise ValueError("mean_component_bound_requires_n_ge_2")
    return math.log(n) + 0.5 * (n - 1)


def period_energy_mean(n: int) -> float:
    """M_N=A_N^2+C_N, the exact full-period mean of R_N^2."""
    if n < 2:
        raise ValueError("period_energy_mean_requires_n_ge_2")
    a_n = mean_component(n)
    return a_n * a_n + gcd_covariance_jordan(n)


def _interval_unweighted_square(
    theta: float,
    constant: float,
    a: float,
    b: float,
) -> float:
    return (
        (theta * theta / 3.0) * (b**3 - a**3)
        - theta * constant * (b**2 - a**2)
        + constant * constant * (b - a)
    )


def _local_discrepancy_increment(
    theta: float,
    constant: float,
    mean_energy: float,
    a: float,
    b: float,
) -> float:
    return (
        _interval_unweighted_square(theta, constant, a, b)
        - mean_energy * (b - a)
    )


def cumulative_energy_discrepancy(n: int, x: float) -> float:
    """E_N(x)=integral_N^x R_N(y)^2dy-M_N(x-N), for x>=N."""
    if n < 2 or x < n:
        raise ValueError("energy_discrepancy_requires_x_ge_n_ge_2")
    if x == n:
        return 0.0
    theta = theta_n(n)
    mean_energy = period_energy_mean(n)
    total = 0.0
    start = float(n)
    full_end = math.floor(x)
    for m in range(n, full_end):
        a = float(m)
        b = float(m + 1)
        constant = psi_n(a, n)
        total += _local_discrepancy_increment(
            theta, constant, mean_energy, a, b
        )
    if x > full_end:
        a = float(full_end)
        constant = psi_n(a, n)
        total += _local_discrepancy_increment(
            theta, constant, mean_energy, a, x
        )
    return total


def discrepancy_periodicity_check(n: int, y: float) -> dict[str, float]:
    """E_N(y+L_N)=E_N(y) for the exact fixed-N period L_N."""
    if y < n:
        raise ValueError("discrepancy_periodicity_requires_y_ge_n")
    period = residual_period(n)
    left = cumulative_energy_discrepancy(n, y)
    right = cumulative_energy_discrepancy(n, y + period)
    return {
        "left": left,
        "right": right,
        "absolute_error": abs(left - right),
    }


def fixed_n_discrepancy_supremum(
    n: int,
    *,
    max_period: int = 200_000,
) -> dict[str, float | int]:
    """Compute sup |E_N| over one full period for modest fixed N.

    On each unit interval E_N'(y)=R_N(y)^2-M_N. Candidate extrema therefore
    occur at the interval endpoints or where R_N(y)=+/-sqrt(M_N).
    """
    if n < 2:
        raise ValueError("discrepancy_supremum_requires_n_ge_2")
    period = residual_period(n)
    if period > max_period:
        raise ValueError("period_too_large_for_discrepancy_supremum")

    theta = theta_n(n)
    mean_energy = period_energy_mean(n)
    root_energy = math.sqrt(max(mean_energy, 0.0))
    running = 0.0
    supremum = 0.0

    for m in range(n, n + period):
        a = float(m)
        b = float(m + 1)
        constant = psi_n(a, n)

        supremum = max(supremum, abs(running))
        if abs(theta) > 1e-15:
            for sign in (-1.0, 1.0):
                candidate = (constant + sign * root_energy) / theta
                if a < candidate < b:
                    local = _local_discrepancy_increment(
                        theta, constant, mean_energy, a, candidate
                    )
                    supremum = max(supremum, abs(running + local))

        running += _local_discrepancy_increment(
            theta, constant, mean_energy, a, b
        )
        supremum = max(supremum, abs(running))

    return {
        "period": period,
        "supremum": supremum,
        "period_endpoint_error": abs(running),
    }


def transfer_error_bound(n: int, discrepancy_supremum: float) -> float:
    """|T_N-M_N/N| <= D_N/N^2 when |E_N(y)|<=D_N."""
    if n < 2 or discrepancy_supremum < 0.0:
        raise ValueError("transfer_error_bound_requires_nonnegative_inputs")
    return discrepancy_supremum / (n * n)


def periodic_transfer_interval(
    n: int,
    *,
    max_period: int = 200_000,
) -> TailAttackIIICertificate:
    """Fixed-N periodic-transfer certificate.

    Exact identity:
        T_N = M_N/N + 2 integral_N^infinity E_N(y)/y^3 dy.
    Since E_N is periodic and |E_N|<=D_N,
        |T_N-M_N/N| <= D_N/N^2.

    The fixed-N certificate does not prove the required N-to-infinity rates.
    """
    discrepancy = fixed_n_discrepancy_supremum(n, max_period=max_period)
    a_n = mean_component(n)
    covariance = gcd_covariance_jordan(n)
    mean_energy = a_n * a_n + covariance
    d_n = float(discrepancy["supremum"])
    error = transfer_error_bound(n, d_n)
    center = mean_energy / n
    log_squared = math.log(n) ** 2
    return TailAttackIIICertificate(
        n=n,
        period=int(discrepancy["period"]),
        mean_component=a_n,
        mean_component_squared=a_n * a_n,
        covariance_component=covariance,
        period_energy_mean=mean_energy,
        discrepancy_supremum=d_n,
        discrepancy_endpoint_error=float(discrepancy["period_endpoint_error"]),
        transfer_lower_bound=max(0.0, center - error),
        transfer_upper_bound=center + error,
        normalized_mean_term=(a_n * a_n / n) / log_squared,
        normalized_discrepancy_term=(d_n / (n * n)) / log_squared,
    )


def mean_target_ratio(n: int) -> float:
    """Finite diagnostic A_N^2/(N log^2 N); evidence only."""
    if n < 2:
        raise ValueError("mean_target_ratio_requires_n_ge_2")
    a_n = mean_component(n)
    return a_n * a_n / (n * math.log(n) ** 2)


def discrepancy_target_ratio(
    n: int,
    *,
    max_period: int = 200_000,
) -> float:
    """Finite diagnostic D_N/(N^2 log^2 N); evidence only."""
    d_n = fixed_n_discrepancy_supremum(
        n, max_period=max_period
    )["supremum"]
    return float(d_n) / (n * n * math.log(n) ** 2)


def tail_attack_iii_snapshot(n: int = 8) -> dict[str, Any]:
    certificate = periodic_transfer_interval(n)
    tail_i = certified_tail_interval(n, max(128, 16 * n))
    mean_direct = mean_component(n)
    mean_mertens = mean_component_mertens_form(n)
    return {
        "phase": "TAIL_ATTACK_III",
        "n": n,
        "decomposition": "R_N(y)=A_N+S_N(y)",
        "mean_component": {
            "A_N": mean_direct,
            "mertens_form": mean_mertens,
            "identity_error": abs(mean_direct - mean_mertens),
            "elementary_upper_bound": elementary_mean_component_bound(n),
            "uniform_target": "A_N^2/N=o(log^2 N), equivalently A_N=o(sqrt(N) log N)",
            "uniform_target_certified": False,
        },
        "period_energy": {
            "A_N_squared": mean_direct * mean_direct,
            "C_N": gcd_covariance_jordan(n),
            "M_N": period_energy_mean(n),
            "identity": "M_N=A_N^2+C_N",
        },
        "transfer": {
            "identity": (
                "T_N=M_N/N+2*integral_N^infinity E_N(y)/y^3 dy"
            ),
            "bound": "|T_N-M_N/N|<=D_N/N^2",
            "certificate": certificate.as_dict(),
            "uniform_discrepancy_target": "D_N=o(N^2 log^2 N)",
            "uniform_discrepancy_target_certified": False,
        },
        "tail_i_cross_check": {
            "lower_bound": tail_i.certified_lower_bound,
            "upper_bound": tail_i.certified_upper_bound,
            "intervals_overlap": (
                certificate.transfer_lower_bound <= tail_i.certified_upper_bound
                and tail_i.certified_lower_bound <= certificate.transfer_upper_bound
            ),
        },
        "proved_reductions": [
            "R_N=A_N+centered_sawtooth_N exactly",
            "A_N=log N+(1/2) integral_1^N M(t)dt/t exactly",
            "M_N=A_N^2+C_N exactly",
            "C_N=O(N) unconditionally from Tail Attack II",
            "E_N is fixed-N periodic",
            "T_N=M_N/N+2 integral E_N/y^3 exactly",
            "|T_N-M_N/N|<=D_N/N^2 for fixed N",
        ],
        "remaining_uniform_gaps": [
            "Prove A_N=o(sqrt(N) log N) or another bound sufficient for A_N^2/N=o(log^2 N).",
            "Prove D_N=o(N^2 log^2 N), or a sharper transfer estimate.",
            "Do not replace either gap with RH, hidden PNT-strength cancellation, or Mobius randomness.",
        ],
        "proof_status": "CONJECTURAL_LEMMA",
        "uniform_tail_certified": False,
    }
