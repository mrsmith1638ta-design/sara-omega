from __future__ import annotations

import math
from typing import Iterable

EULER_GAMMA = 0.577215664901532860606512090082402431


def v_k(k: int) -> float:
    """<chi_(0,1), rho_k> for rho_k(x)={1/(kx)}."""
    if k < 1:
        raise ValueError("k_must_be_positive")
    return (math.log(k) + 1.0 - EULER_GAMMA) / k


def vasyunin_sum(a: int, b: int) -> float:
    """V(a,b)=sum_{r=1}^{b-1} {ra/b} cot(pi r/b)."""
    if a < 1 or b < 1:
        raise ValueError("vasyunin_arguments_must_be_positive")
    if b == 1:
        return 0.0
    total = 0.0
    for r in range(1, b):
        frac = ((r * a) % b) / b
        total += frac / math.tan(math.pi * r / b)
    return total


def gram_entry(j: int, k: int) -> float:
    """Exact Vasyunin-formula evaluation of <rho_j,rho_k>.

    The coprime formula is reduced by gcd scaling:
    <rho_(dp),rho_(dq)> = <rho_p,rho_q>/d.
    """
    if j < 1 or k < 1:
        raise ValueError("gram_indices_must_be_positive")
    d = math.gcd(j, k)
    p, q = j // d, k // d
    core = (
        0.5 * (math.log(2.0 * math.pi) - EULER_GAMMA) * (1.0 / p + 1.0 / q)
        + ((p - q) / (2.0 * p * q)) * math.log(q / p)
        - (math.pi / (2.0 * p * q)) * (vasyunin_sum(q, p) + vasyunin_sum(p, q))
    )
    return core / d


def gram_matrix(n: int) -> list[list[float]]:
    if n < 1:
        raise ValueError("n_must_be_positive")
    return [[gram_entry(j, k) for k in range(1, n + 1)] for j in range(1, n + 1)]


def v_vector(n: int) -> list[float]:
    if n < 1:
        raise ValueError("n_must_be_positive")
    return [v_k(k) for k in range(1, n + 1)]


def dot(a: Iterable[float], b: Iterable[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [dot(row, vector) for row in matrix]


def solve_linear(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    n = len(matrix)
    if n == 0 or len(rhs) != n or any(len(row) != n for row in matrix):
        raise ValueError("linear_system_dimension_mismatch")
    a = [list(row) + [float(rhs[i])] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-14:
            raise ValueError("singular_gram_matrix")
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
        p = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= p
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def determinant(matrix: list[list[float]]) -> float:
    n = len(matrix)
    if n == 0 or any(len(row) != n for row in matrix):
        raise ValueError("determinant_requires_square_matrix")
    a = [list(row) for row in matrix]
    det = 1.0
    sign = 1.0
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-15:
            return 0.0
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
            sign *= -1.0
        p = a[col][col]
        det *= p
        for row in range(col + 1, n):
            factor = a[row][col] / p
            for j in range(col + 1, n):
                a[row][j] -= factor * a[col][j]
    return sign * det


def optimal_coefficients(n: int) -> list[float]:
    g = gram_matrix(n)
    return solve_linear(g, v_vector(n))


def d_squared(n: int) -> float:
    g = gram_matrix(n)
    v = v_vector(n)
    c = solve_linear(g, v)
    value = 1.0 - dot(v, c)
    if -1e-12 < value < 0.0:
        value = 0.0
    return value


def q_n(a: list[float]) -> float:
    """Q_N(a)=d_N^2+(a-c_N)^T G_N(a-c_N)."""
    n = len(a)
    if n < 1:
        raise ValueError("coefficient_vector_must_be_nonempty")
    g = gram_matrix(n)
    v = v_vector(n)
    c = solve_linear(g, v)
    delta = [a[i] - c[i] for i in range(n)]
    return d_squared(n) + dot(delta, matvec(g, delta))


def residual_against_negative_mobius(mu: list[int]) -> dict[str, list[float]]:
    """r_N=v_N-G_N(-mu), delta_N=G_N^{-1}r_N."""
    n = len(mu) - 1
    if n < 1:
        raise ValueError("mobius_vector_must_be_one_indexed")
    baseline = [-float(mu[k]) for k in range(1, n + 1)]
    g = gram_matrix(n)
    v = v_vector(n)
    gb = matvec(g, baseline)
    residual = [v[i] - gb[i] for i in range(n)]
    correction = solve_linear(g, residual)
    return {"baseline": baseline, "residual": residual, "correction": correction}


def augmented_gram(n: int) -> list[list[float]]:
    """[[1,v^T],[v,G]] whose determinant ratio equals d_N^2."""
    g = gram_matrix(n)
    v = v_vector(n)
    return [[1.0, *v], *[[v[i], *g[i]] for i in range(n)]]


def determinant_ratio_d_squared(n: int) -> float:
    return determinant(augmented_gram(n)) / determinant(gram_matrix(n))


def schur_extension(n: int) -> dict[str, float]:
    """One-step Schur decrement from N to N+1."""
    if n < 1:
        raise ValueError("n_must_be_positive")
    g = gram_matrix(n)
    v = v_vector(n)
    g_inv_v = solve_linear(g, v)
    edge = [gram_entry(k, n + 1) for k in range(1, n + 1)]
    g_inv_edge = solve_linear(g, edge)
    a_n = gram_entry(n + 1, n + 1)
    b_n = v_k(n + 1)
    s_n = a_n - dot(edge, g_inv_edge)
    t_n = b_n - dot(edge, g_inv_v)
    if s_n <= 0.0:
        raise ValueError("nonpositive_schur_complement")
    current = d_squared(n)
    recursive_next = current - (t_n * t_n) / s_n
    direct_next = d_squared(n + 1)
    return {
        "s_n": s_n,
        "t_n": t_n,
        "d_n_squared": current,
        "recursive_next_d_squared": recursive_next,
        "direct_next_d_squared": direct_next,
        "absolute_error": abs(recursive_next - direct_next),
    }
