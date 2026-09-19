from __future__ import annotations

import math


def _prime_factorization(n: int) -> dict[int, int]:
    factors: dict[int, int] = {}
    d = 2
    value = n
    while d * d <= value:
        while value % d == 0:
            factors[d] = factors.get(d, 0) + 1
            value //= d
        d += 1 if d == 2 else 2
    if value > 1:
        factors[value] = factors.get(value, 0) + 1
    return factors


def mobius(n: int) -> int:
    if n < 1:
        raise ValueError("n must be positive")
    if n == 1:
        return 1
    factors = _prime_factorization(n)
    if any(power > 1 for power in factors.values()):
        return 0
    return -1 if len(factors) % 2 else 1


def mobius_values(n: int) -> list[int]:
    if n < 1:
        raise ValueError("n must be positive")
    return [mobius(k) for k in range(1, n + 1)]


def von_mangoldt(n: int) -> float:
    if n < 1:
        raise ValueError("n must be positive")
    factors = _prime_factorization(n)
    if len(factors) == 1:
        prime, _ = next(iter(factors.items()))
        return math.log(prime)
    return 0.0


def chebyshev_psi(y: int) -> float:
    if y < 1:
        raise ValueError("y must be positive")
    return sum(von_mangoldt(k) for k in range(1, y + 1))


def chebyshev_psi_values(n: int) -> list[float]:
    if n < 1:
        raise ValueError("n must be positive")
    running = 0.0
    out: list[float] = []
    for k in range(1, n + 1):
        running += von_mangoldt(k)
        out.append(running)
    return out

