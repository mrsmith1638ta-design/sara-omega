from __future__ import annotations

import math

from .mobius import mobius_values


def _require_N(N: int) -> None:
    if N < 2:
        raise ValueError("N must be at least 2 for log(N)-weighted coefficients")


def selberg_coefficients(N: int) -> list[float]:
    _require_N(N)
    logN = math.log(N)
    return [-mu * (1.0 - math.log(n) / logN) for n, mu in enumerate(mobius_values(N), start=1)]


def theta_N(N: int) -> float:
    _require_N(N)
    logN = math.log(N)
    total = 0.0
    for n, c in enumerate(selberg_coefficients(N), start=1):
        total += c / n
    return -logN * total


def finite_psi_N(N: int, y: int) -> float:
    _require_N(N)
    if y < 1:
        raise ValueError("y must be positive")
    logN = math.log(N)
    mu = mobius_values(N)
    divisor_sum = sum(mu[n - 1] * (y // n) for n in range(1, N + 1))
    log_sum = sum(mu[n - 1] * math.log(n) * (y // n) for n in range(1, N + 1))
    return -logN + logN * divisor_sum - log_sum

