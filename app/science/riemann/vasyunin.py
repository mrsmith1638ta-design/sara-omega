from __future__ import annotations

import math

from .mobius import mobius_values
from .models import RiemannComputationFailure, RiemannProofStatus, RiemannResult


def rho(n: int, x: float) -> float:
    if n < 1:
        raise ValueError("n must be positive")
    if not 0.0 < x < 1.0:
        raise ValueError("x must lie in (0, 1)")
    value = 1.0 / (n * x)
    return value - math.floor(value)


def _midpoints(samples: int) -> list[float]:
    if samples < 16:
        raise RiemannComputationFailure("samples must be at least 16")
    return [(i + 0.5) / samples for i in range(samples)]


def gram_entry(j: int, k: int, samples: int = 4096) -> float:
    xs = _midpoints(samples)
    return sum(rho(j, x) * rho(k, x) for x in xs) / samples


def gram_matrix(N: int, samples: int = 4096) -> list[list[float]]:
    if N < 1:
        raise RiemannComputationFailure("N must be positive")
    G = [[0.0 for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i, N):
            entry = gram_entry(i + 1, j + 1, samples=samples)
            G[i][j] = entry
            G[j][i] = entry
    return G


def target_vector(N: int, samples: int = 4096) -> list[float]:
    if N < 1:
        raise RiemannComputationFailure("N must be positive")
    xs = _midpoints(samples)
    return [sum(rho(k, x) for x in xs) / samples for k in range(1, N + 1)]


def _matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def mobius_residual(N: int, samples: int = 4096) -> RiemannResult:
    if N < 1:
        raise RiemannComputationFailure("N must be positive")
    G = gram_matrix(N, samples=samples)
    v = target_vector(N, samples=samples)
    m = [-mu for mu in mobius_values(N)]
    Gm = _matvec(G, [float(item) for item in m])
    residual = [v[i] - Gm[i] for i in range(N)]
    energy = sum(item * item for item in residual)
    return RiemannResult(
        statement=f"Finite Vasyunin residual r_N = v_N - G_N m_N computed for N={N}.",
        status=RiemannProofStatus.NUMERICAL_EVIDENCE,
        evidence=["bounded midpoint quadrature", "finite Gram computation"],
        limitations=["Finite numerical evidence cannot establish d_N -> 0 or RH."],
        metadata={"N": N, "samples": samples, "residual_l2_squared": energy, "r_N": residual},
    )


def schur_decrement_record(N: int) -> RiemannResult:
    return RiemannResult(
        statement=f"The Schur decrement identity d_(N+1)^2 = d_N^2 - t_N^2/s_N is tracked at N={N}.",
        status=RiemannProofStatus.SYMBOLIC_IDENTITY,
        evidence=["block inverse Schur complement identity"],
        limitations=["This record does not certify lower bounds for cumulative decrements."],
        metadata={"N": N},
    )

