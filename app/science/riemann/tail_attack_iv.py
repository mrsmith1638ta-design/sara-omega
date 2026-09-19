from __future__ import annotations

import math
from typing import Any, Iterable

from .gcd_covariance import COVARIANCE_LINEAR_CONSTANT, gcd_covariance_jordan
from .tail_attack import residual_period
from .tail_attack_iii import (
    _local_discrepancy_increment,
    fixed_n_discrepancy_supremum,
    mean_component,
    period_energy_mean,
)
from .baez_duarte import psi_n, theta_n


PROVED = "proved"
FINITE_CERTIFIED = "finite_certified"
CONJECTURAL = "conjectural"
BLOCKED = "blocked"


def known_mertens_bound_catalog() -> list[dict[str, Any]]:
    """Sourced comparison ladder for the mean-component route.

    The catalog deliberately separates established external results from the
    stronger rate needed by Tail Attack IV.
    """
    return [
        {
            "bound_id": "elementary_trivial",
            "statement": "|M(x)| <= x",
            "status": PROVED,
            "source": "elementary from |mu(n)|<=1",
            "implied_mean_scale": "A_N=O(N)",
            "reaches_tail_iv_mean_target": False,
        },
        {
            "bound_id": "prime_number_theorem",
            "statement": "M(x)=o(x)",
            "status": PROVED,
            "source": "Prime Number Theorem / classical equivalent formulation",
            "source_url": "https://encyclopediaofmath.org/wiki/Wirsing_theorems",
            "implied_mean_scale": "A_N=o(N)",
            "reaches_tail_iv_mean_target": False,
        },
        {
            "bound_id": "korobov_vinogradov_zero_free_region",
            "statement": (
                "M(x) << x exp(-c (log x)^(3/5) (log log x)^(-1/5)) "
                "for some c>0"
            ),
            "status": PROVED,
            "source": "Walfisz / Korobov-Vinogradov zero-free-region method",
            "source_url": "https://arxiv.org/abs/2208.06141",
            "implied_mean_scale": (
                "A_N has the same broad N*subexponential-decay scale"
            ),
            "reaches_tail_iv_mean_target": False,
        },
        {
            "bound_id": "tail_iv_required_mean_rate",
            "statement": "A_N=o(sqrt(N) log N)",
            "status": CONJECTURAL,
            "source": "SARA Tail Attack IV proof dependency",
            "rh_sensitive": True,
            "reaches_tail_iv_mean_target": True,
            "notes": (
                "Do not import this from generic Mobius cancellation. "
                "The weighted Mobius transform contains 1/zeta(s)."
            ),
        },
    ]


def weighted_mobius_mellin_statement() -> dict[str, str]:
    """Exact transform exposing zero sensitivity of the mean component."""
    return {
        "definition": "W(x)=sum_{n<=x} mu(n) log(x/n)",
        "transform": (
            "integral_1^infinity W(x) x^(-s-1) dx = 1/(s^2 zeta(s)), Re(s)>1"
        ),
        "status": PROVED,
        "warning": (
            "Bounds near the sqrt(x) scale are zeta-zero sensitive and must not "
            "be assumed as routine PNT input."
        ),
    }


def deterministic_period_discrepancy_bound(n: int) -> float:
    """Unconditional fixed-N bound D_N <= 2 L_N M_N.

    Over one full period L_N,
      int R_N^2 = M_N L_N.
    For any partial period,
      |int (R_N^2-M_N)| <= int R_N^2 + M_N*length <= 2 M_N L_N.
    This is structurally valid but asymptotically weak because L_N grows fast.
    """
    if n < 2:
        raise ValueError("period_discrepancy_bound_requires_n_ge_2")
    return 2.0 * residual_period(n) * period_energy_mean(n)


def _unit_discrepancy_increments(n: int, *, max_period: int = 200_000) -> list[float]:
    period = residual_period(n)
    if period > max_period:
        raise ValueError("period_too_large_for_subperiod_profile")
    theta = theta_n(n)
    mean_energy = period_energy_mean(n)
    increments: list[float] = []
    for m in range(n, n + period):
        a = float(m)
        b = float(m + 1)
        constant = psi_n(a, n)
        increments.append(
            _local_discrepancy_increment(theta, constant, mean_energy, a, b)
        )
    return increments


def subperiod_discrepancy_profile(
    n: int,
    *,
    block_sizes: Iterable[int] | None = None,
    max_period: int = 200_000,
) -> list[dict[str, float | int | str]]:
    """Finite deterministic block-balance diagnostics over one full period."""
    period = residual_period(n)
    increments = _unit_discrepancy_increments(n, max_period=max_period)

    if block_sizes is None:
        candidates = [1, 2, 4, 8, 16, 32, 64, period]
        sizes = sorted({b for b in candidates if 1 <= b <= period})
    else:
        sizes = sorted({int(b) for b in block_sizes if 1 <= int(b) <= period})
    if not sizes:
        raise ValueError("subperiod_profile_requires_at_least_one_block_size")

    rows: list[dict[str, float | int | str]] = []
    for block in sizes:
        prefix = [0.0]
        for value in increments:
            prefix.append(prefix[-1] + value)
        max_abs = 0.0
        for start in range(0, period - block + 1):
            block_sum = prefix[start + block] - prefix[start]
            max_abs = max(max_abs, abs(block_sum))
        rows.append({
            "block_size": block,
            "max_absolute_block_discrepancy": max_abs,
            "normalized_by_block": max_abs / block,
            "status": FINITE_CERTIFIED,
        })
    return rows


def mean_growth_snapshot(ns: Iterable[int]) -> list[dict[str, float | int]]:
    """Finite-N mean-component diagnostics only."""
    rows: list[dict[str, float | int]] = []
    for n in ns:
        if n < 2:
            raise ValueError("mean_growth_snapshot_requires_n_ge_2")
        a_n = mean_component(n)
        rows.append({
            "n": n,
            "A_N": a_n,
            "A_N_squared_over_N": a_n * a_n / n,
            "target_ratio": a_n * a_n / (n * math.log(n) ** 2),
        })
    return rows


def discrepancy_growth_snapshot(
    ns: Iterable[int],
    *,
    max_period: int = 200_000,
) -> list[dict[str, float | int]]:
    """Finite-N exact D_N diagnostics where the full period is tractable."""
    rows: list[dict[str, float | int]] = []
    for n in ns:
        if n < 2:
            raise ValueError("discrepancy_growth_snapshot_requires_n_ge_2")
        period = residual_period(n)
        if period > max_period:
            continue
        result = fixed_n_discrepancy_supremum(n, max_period=max_period)
        d_n = float(result["supremum"])
        rows.append({
            "n": n,
            "period": period,
            "D_N": d_n,
            "D_N_over_N_squared": d_n / (n * n),
            "target_ratio": d_n / (n * n * math.log(n) ** 2),
        })
    return rows


def combined_tail_dashboard(n: int = 8) -> dict[str, Any]:
    """Live proof-dependency dashboard for T_N.

    Uses the exact Tail Attack III inequality
        T_N <= A_N^2/N + C_N/N + D_N/N^2
    with component-level proof labels.
    """
    if n < 2:
        raise ValueError("dashboard_requires_n_ge_2")

    a_n = mean_component(n)
    c_n = gcd_covariance_jordan(n)
    discrepancy = fixed_n_discrepancy_supremum(n)
    d_n = float(discrepancy["supremum"])

    mean_term = a_n * a_n / n
    covariance_term = c_n / n
    discrepancy_term = d_n / (n * n)
    total = mean_term + covariance_term + discrepancy_term

    return {
        "phase": "TAIL_ATTACK_IV",
        "n": n,
        "inequality": "T_N <= A_N^2/N + C_N/N + D_N/N^2",
        "terms": {
            "mean": {
                "symbol": "A_N^2/N",
                "value": mean_term,
                "finite_status": FINITE_CERTIFIED,
                "uniform_status": BLOCKED,
                "target": "o(log^2 N)",
                "reason": (
                    "Known unconditional Mertens bounds do not reach "
                    "A_N=o(sqrt(N) log N); near-sqrt bounds are zeta-zero sensitive."
                ),
            },
            "covariance": {
                "symbol": "C_N/N",
                "value": covariance_term,
                "finite_status": FINITE_CERTIFIED,
                "uniform_status": PROVED,
                "uniform_bound": f"<= {COVARIANCE_LINEAR_CONSTANT:.12f}",
                "target": "o(log^2 N)",
                "reason": "Tail Attack II proves C_N=O(N) unconditionally.",
            },
            "discrepancy": {
                "symbol": "D_N/N^2",
                "value": discrepancy_term,
                "finite_status": FINITE_CERTIFIED,
                "uniform_status": CONJECTURAL,
                "target": "o(log^2 N)",
                "reason": (
                    "D_N is exactly certified at this fixed N, but no uniform "
                    "subperiod/period-growth theorem is proved."
                ),
            },
        },
        "finite_upper_bound": total,
        "finite_upper_status": FINITE_CERTIFIED,
        "uniform_tail_status": BLOCKED,
        "uniform_tail_certified": False,
        "dependency_graph": {
            "tail_target": [
                "mean_uniform_target",
                "covariance_uniform_bound",
                "discrepancy_uniform_target",
            ],
            "mean_uniform_target": {
                "status": BLOCKED,
                "requirement": "A_N^2/N=o(log^2 N)",
            },
            "covariance_uniform_bound": {
                "status": PROVED,
                "requirement": "C_N=O(N)",
            },
            "discrepancy_uniform_target": {
                "status": CONJECTURAL,
                "requirement": "D_N/N^2=o(log^2 N)",
            },
        },
    }


def tail_attack_iv_snapshot(n: int = 8) -> dict[str, Any]:
    dashboard = combined_tail_dashboard(n)
    return {
        "phase": "TAIL_ATTACK_IV",
        "program": "Mean + Discrepancy Growth Program",
        "mertens_bound_catalog": known_mertens_bound_catalog(),
        "weighted_mobius_mellin": weighted_mobius_mellin_statement(),
        "mean_growth": mean_growth_snapshot((8, 16, 32, 64, 128)),
        "discrepancy_growth": discrepancy_growth_snapshot((4, 6, 8, 10, 12)),
        "subperiod_profile": subperiod_discrepancy_profile(n),
        "deterministic_period_discrepancy_bound": {
            "value": deterministic_period_discrepancy_bound(n),
            "status": PROVED,
            "asymptotically_sufficient": False,
            "reason": "Contains the rapidly growing lcm period L_N.",
        },
        "dashboard": dashboard,
        "red_team_rules": [
            "No unsourced Mertens/PNT/zero-free-region bound may be promoted.",
            "No RH or zeta-zero-location assumption may fill the mean target.",
            "No Mobius-randomness or square-root-cancellation assumption may fill the mean target.",
            "No finite period or subperiod pattern may prove a uniform D_N rate.",
            "No combined tail theorem may pass while any required term remains blocked or conjectural.",
        ],
        "uniform_tail_certified": False,
    }
