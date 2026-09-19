from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from .baez_duarte import mobius_sieve
from .tail_attack import period_mean_square, tail_weights


LN2 = math.log(2.0)
COVARIANCE_LINEAR_CONSTANT = (
    12.0 * LN2**2 + 104.0 * LN2**3 + 300.0 * LN2**4
) / 12.0


@dataclass(frozen=True)
class GCDCovarianceCertificate:
    n: int
    direct_covariance: float | None
    jordan_covariance: float
    coprime_layer_covariance: float
    linear_upper_bound: float
    linear_bound_constant: float
    jordan_direct_absolute_error: float | None
    jordan_coprime_absolute_error: float
    max_layer_identity_error: float
    proof_status: str = "SYMBOLIC_IDENTITY"
    uniform_tail_certified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "direct_covariance": self.direct_covariance,
            "jordan_covariance": self.jordan_covariance,
            "coprime_layer_covariance": self.coprime_layer_covariance,
            "linear_upper_bound": self.linear_upper_bound,
            "linear_bound_constant": self.linear_bound_constant,
            "jordan_direct_absolute_error": self.jordan_direct_absolute_error,
            "jordan_coprime_absolute_error": self.jordan_coprime_absolute_error,
            "max_layer_identity_error": self.max_layer_identity_error,
            "proof_status": self.proof_status,
            "uniform_tail_certified": self.uniform_tail_certified,
        }


def jordan_totient_2_sieve(n: int) -> list[int]:
    """Return J_2(k)=k^2 prod_{p|k}(1-p^-2), for 0<=k<=n."""
    if n < 1:
        raise ValueError("jordan_totient_requires_positive_n")
    values = [k * k for k in range(n + 1)]
    values[0] = 0
    is_prime = [True] * (n + 1)
    if n >= 1:
        is_prime[0] = False
    if n >= 1:
        is_prime[1] = False
    for p in range(2, n + 1):
        if not is_prime[p]:
            continue
        for multiple in range(p * 2, n + 1, p):
            is_prime[multiple] = False
        p2 = p * p
        for multiple in range(p, n + 1, p):
            values[multiple] = values[multiple] * (p2 - 1) // p2
    return values


def divisor_layer_sums(n: int) -> list[float]:
    """S_d(N)=sum_{m<=N,d|m} a_m/m for every divisor layer d."""
    if n < 2:
        raise ValueError("divisor_layers_require_n_ge_2")
    weights = tail_weights(n)
    layers = [0.0] * (n + 1)
    for d in range(1, n + 1):
        layers[d] = sum(
            weights[m] / m
            for m in range(d, n + 1, d)
        )
    return layers


def coprime_mobius_layer(n: int, d: int) -> float:
    """H_d(N/d)=sum_{k<=N/d,(k,d)=1} mu(k) log((N/d)/k)/k.

    For squarefree d,
        S_d(N)=mu(d)/d * H_d(N/d).
    For nonsquarefree d, S_d(N)=0 because every multiple has zero Mobius value.
    """
    if n < 2 or d < 1 or d > n:
        raise ValueError("coprime_layer_requires_1_le_d_le_n")
    mu = mobius_sieve(n)
    if mu[d] == 0:
        return 0.0
    limit = n // d
    log_x = math.log(n / d)
    return sum(
        mu[k] * (log_x - math.log(k)) / k
        for k in range(1, limit + 1)
        if math.gcd(k, d) == 1
    )


def gcd_covariance_direct(n: int) -> float:
    """Direct O(N^2) evaluation of (1/12) sum a_m a_n gcd(m,n)^2/(mn)."""
    if n < 2:
        raise ValueError("gcd_covariance_requires_n_ge_2")
    weights = tail_weights(n)
    total = 0.0
    for m in range(1, n + 1):
        if weights[m] == 0.0:
            continue
        for k in range(1, n + 1):
            if weights[k] == 0.0:
                continue
            total += (
                weights[m]
                * weights[k]
                * (math.gcd(m, k) ** 2)
                / (m * k)
            )
    return total / 12.0


def gcd_covariance_jordan(n: int) -> float:
    """Exact Jordan-totient decomposition of the gcd covariance.

    gcd(m,n)^2=sum_{d|m,d|n} J_2(d), so
        C_N=(1/12) sum_{d<=N} J_2(d) S_d(N)^2.
    This proves positive semidefiniteness of the covariance form.
    """
    if n < 2:
        raise ValueError("gcd_covariance_requires_n_ge_2")
    j2 = jordan_totient_2_sieve(n)
    layers = divisor_layer_sums(n)
    return sum(j2[d] * layers[d] ** 2 for d in range(1, n + 1)) / 12.0


def gcd_covariance_coprime_layers(n: int) -> float:
    """Equivalent squarefree/coprime layer decomposition.

    C_N=(1/12) sum_{d squarefree<=N} J_2(d)/d^2 * H_d(N/d)^2.
    """
    if n < 2:
        raise ValueError("gcd_covariance_requires_n_ge_2")
    mu = mobius_sieve(n)
    j2 = jordan_totient_2_sieve(n)
    total = 0.0
    for d in range(1, n + 1):
        if mu[d] == 0:
            continue
        h_d = coprime_mobius_layer(n, d)
        total += (j2[d] / (d * d)) * h_d * h_d
    return total / 12.0


def max_layer_identity_error(n: int) -> float:
    """Numerically verify S_d=mu(d)H_d/d across all layers."""
    if n < 2:
        raise ValueError("layer_identity_requires_n_ge_2")
    mu = mobius_sieve(n)
    layers = divisor_layer_sums(n)
    error = 0.0
    for d in range(1, n + 1):
        predicted = 0.0
        if mu[d] != 0:
            predicted = mu[d] * coprime_mobius_layer(n, d) / d
        error = max(error, abs(layers[d] - predicted))
    return error


def harmonic_layer_upper_bound(n: int, d: int) -> float:
    """Elementary unconditional bound |H_d| <= L_d(1+L_d)."""
    if n < 2 or d < 1 or d > n:
        raise ValueError("harmonic_layer_bound_requires_1_le_d_le_n")
    log_ratio = math.log(n / d)
    return log_ratio * (1.0 + log_ratio)


def covariance_linear_upper_bound(n: int) -> float:
    """Uniform unconditional C_N <= K*N with explicit K.

    Proof sketch:
      |H_d| <= log(N/d)(1+log(N/d)),
      J_2(d)/d^2 <= 1,
    then dyadically group d by N/2^(j+1) < d <= N/2^j.
    The convergent geometric moments are
      sum (j+1)^2/2^j = 12,
      sum (j+1)^3/2^j = 52,
      sum (j+1)^4/2^j = 300.
    """
    if n < 2:
        raise ValueError("covariance_bound_requires_n_ge_2")
    return COVARIANCE_LINEAR_CONSTANT * n


def layer_contributions(n: int, *, limit: int = 12) -> list[dict[str, float | int]]:
    """Largest nonnegative Jordan-layer contributions to C_N."""
    if n < 2 or limit < 1:
        raise ValueError("layer_contributions_require_n_ge_2_and_positive_limit")
    j2 = jordan_totient_2_sieve(n)
    layers = divisor_layer_sums(n)
    mu = mobius_sieve(n)
    rows: list[dict[str, float | int]] = []
    for d in range(1, n + 1):
        contribution = j2[d] * layers[d] ** 2 / 12.0
        if contribution == 0.0:
            continue
        h_d = coprime_mobius_layer(n, d) if mu[d] != 0 else 0.0
        rows.append({
            "d": d,
            "jordan_weight": j2[d] / (d * d),
            "divisor_layer_sum": layers[d],
            "coprime_mobius_layer": h_d,
            "contribution": contribution,
        })
    rows.sort(key=lambda row: float(row["contribution"]), reverse=True)
    return rows[:limit]


def covariance_sequence(ns: Iterable[int]) -> list[dict[str, float | int]]:
    """Finite-N diagnostics only; never an asymptotic proof."""
    rows: list[dict[str, float | int]] = []
    for n in ns:
        if n < 2:
            raise ValueError("covariance_sequence_requires_n_ge_2")
        covariance = gcd_covariance_jordan(n)
        rows.append({
            "n": n,
            "covariance": covariance,
            "covariance_over_n": covariance / n,
            "covariance_over_log_squared": covariance / (math.log(n) ** 2),
            "linear_upper_bound": covariance_linear_upper_bound(n),
        })
    return rows


def conditional_tail_transfer_bound(
    n: int,
    *,
    mean_square: float,
    discrepancy_bound: float,
) -> float:
    """Conditional Abel/integration-by-parts transfer.

    If for every x>=N,
      A_N(x)=int_N^x R_N(y)^2 dy <= mean_square*(x-N)+discrepancy_bound,
    then
      T_N <= mean_square/N + discrepancy_bound/N^2.

    The function only evaluates the right-hand side; it does not certify the
    required discrepancy hypothesis.
    """
    if n < 2 or mean_square < 0.0 or discrepancy_bound < 0.0:
        raise ValueError("tail_transfer_requires_nonnegative_inputs")
    return mean_square / n + discrepancy_bound / (n * n)


def covariance_certificate(n: int = 32, *, direct_limit: int = 128) -> GCDCovarianceCertificate:
    jordan = gcd_covariance_jordan(n)
    coprime = gcd_covariance_coprime_layers(n)
    direct = gcd_covariance_direct(n) if n <= direct_limit else None
    return GCDCovarianceCertificate(
        n=n,
        direct_covariance=direct,
        jordan_covariance=jordan,
        coprime_layer_covariance=coprime,
        linear_upper_bound=covariance_linear_upper_bound(n),
        linear_bound_constant=COVARIANCE_LINEAR_CONSTANT,
        jordan_direct_absolute_error=None if direct is None else abs(jordan - direct),
        jordan_coprime_absolute_error=abs(jordan - coprime),
        max_layer_identity_error=max_layer_identity_error(n),
    )


def tail_attack_ii_snapshot(n: int = 32) -> dict[str, Any]:
    certificate = covariance_certificate(n)
    mean_square = period_mean_square(n)
    weights = tail_weights(n)
    mean_component = math.log(n) + 0.5 * sum(weights[1:])
    return {
        "phase": "TAIL_ATTACK_II",
        "n": n,
        "certificate": certificate.as_dict(),
        "period_mean_square": mean_square,
        "period_mean_component_squared": mean_component * mean_component,
        "covariance_component": certificate.jordan_covariance,
        "exact_decomposition": (
            "C_N=(1/12) sum_{d<=N} J_2(d) S_d(N)^2"
        ),
        "squarefree_decomposition": (
            "C_N=(1/12) sum_{d squarefree<=N} "
            "J_2(d)/d^2 * H_d(N/d)^2"
        ),
        "uniform_covariance_bound": (
            f"C_N <= K*N with K={COVARIANCE_LINEAR_CONSTANT:.12f}"
        ),
        "cross_layer_cancellation": False,
        "cancellation_location": "inside the coprime Mobius layer sums H_d only",
        "uniform_tail_certified": False,
        "remaining_uniform_gaps": [
            "Control the period mean component uniformly strongly enough for the tail target.",
            "Prove a uniform cumulative-energy discrepancy bound or another valid period-to-tail transfer.",
            "Do not infer T_N=o(log^2 N) from C_N=O(N) alone.",
        ],
        "proof_boundary": (
            "The covariance O(N) bound is unconditional; the transfer from period statistics "
            "to T_N=o(log^2 N) is not certified."
        ),
        "top_layers": layer_contributions(n),
        "finite_sequence": covariance_sequence((8, 16, 32, 64)),
    }
