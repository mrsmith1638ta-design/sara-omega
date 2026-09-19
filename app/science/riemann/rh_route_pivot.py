from __future__ import annotations

import math
from typing import Any

from .vasyunin import d_squared, dot, gram_matrix, matvec, solve_linear, v_vector


FINITE_CERTIFIED = "finite_certified"
CONJECTURAL = "conjectural"
RESEARCH_TARGET = "research_target"


def _distance_squared(coefficients: list[float]) -> float:
    g = gram_matrix(len(coefficients))
    v = v_vector(len(coefficients))
    value = 1.0 - 2.0 * dot(v, coefficients) + dot(coefficients, matvec(g, coefficients))
    if -1e-10 < value < 0.0:
        value = 0.0
    return value


def _constraint_columns(n: int, *, enforce_sum_over_n_zero: bool) -> tuple[list[list[float]], list[float], list[str]]:
    columns = [[1.0 for _ in range(n)]]
    targets = [2.0]
    labels = ["sum_c_equals_2"]
    if enforce_sum_over_n_zero:
        columns.append([1.0 / k for k in range(1, n + 1)])
        targets.append(0.0)
        labels.append("sum_c_over_n_equals_0")
    return columns, targets, labels


def constrained_gram_solution(
    n: int,
    *,
    enforce_sum_over_n_zero: bool = True,
) -> dict[str, Any]:
    """Solve the finite constrained Vasyunin Gram problem.

    Minimize Q_N(c)=1-2v^T c+c^T Gc subject to the algebraic constraints.
    The KKT system is

        [G A][c] = [v]
        [A^T 0][lambda] [b].

    This is a finite-N diagnostic and does not prove an asymptotic penalty.
    """
    if n < 2:
        raise ValueError("constrained_gram_requires_n_ge_2")
    columns, targets, labels = _constraint_columns(
        n,
        enforce_sum_over_n_zero=enforce_sum_over_n_zero,
    )
    g = gram_matrix(n)
    v = v_vector(n)
    m = len(columns)
    block: list[list[float]] = []
    for i in range(n):
        block.append([*g[i], *[columns[j][i] for j in range(m)]])
    for j in range(m):
        block.append([*columns[j], *[0.0 for _ in range(m)]])
    rhs = [*v, *targets]
    solution = solve_linear(block, rhs)
    coefficients = solution[:n]
    multipliers = solution[n:]
    constrained = _distance_squared(coefficients)
    unconstrained = d_squared(n)
    penalty = constrained - unconstrained
    if -1e-10 < penalty < 0.0:
        penalty = 0.0

    constraints = {"sum_c": sum(coefficients)}
    if enforce_sum_over_n_zero:
        constraints["sum_c_over_n"] = sum(coefficients[k - 1] / k for k in range(1, n + 1))

    return {
        "n": n,
        "constraint_labels": labels,
        "coefficients": coefficients,
        "lagrange_multipliers": multipliers,
        "constraints": constraints,
        "constrained_distance_squared": constrained,
        "unconstrained_distance_squared": unconstrained,
        "penalty": penalty,
        "penalty_ratio_over_log_squared": penalty / (math.log(n) ** 2),
        "finite_status": FINITE_CERTIFIED,
        "uniform_status": CONJECTURAL,
        "proof_status": "NUMERICAL_EVIDENCE",
        "asymptotic_certified": False,
    }


def pivot_b_snapshot(n: int = 8) -> dict[str, Any]:
    """Mean-zero constrained coefficient experiment."""
    return {
        "phase": "RH_ROUTE_PIVOT_B",
        "primary_experiment": "mean-zero constrained coefficients",
        "central_question": "Does the constrained approximation penalty tend to zero?",
        "sum_constraint_only": constrained_gram_solution(
            n,
            enforce_sum_over_n_zero=False,
        ),
        "sum_and_reciprocal_constraint": constrained_gram_solution(
            n,
            enforce_sum_over_n_zero=True,
        ),
        "finite_status": FINITE_CERTIFIED,
        "uniform_status": CONJECTURAL,
        "proof_boundary": (
            "Finite constrained penalties are diagnostics only; an RH route would "
            "need a theorem that the penalty tends to zero."
        ),
    }


def rh_route_pivot_snapshot(n: int = 8) -> dict[str, Any]:
    """New route split after stopping the Tail Attack I-V sequence."""
    pivot_b = pivot_b_snapshot(n)
    return {
        "phase": "RH_ROUTE_PIVOT",
        "not_tail_attack_vi": True,
        "reason_for_pivot": (
            "Tail Attack I-V isolated the old route's obstruction: covariance "
            "is reduced, mean appears RH-strength, and discrepancy remains open."
        ),
        "pivot_a": {
            "name": "Signed Cancellation Recovery",
            "status": RESEARCH_TARGET,
            "target": (
                "Analyze the exact signed transfer integral and cross terms "
                "instead of replacing them by D_N/N^2."
            ),
        },
        "pivot_b": {
            "name": "Mean-Zero Constrained Coefficients",
            "status": CONJECTURAL,
            "uniform_status": CONJECTURAL,
            "central_question": pivot_b["central_question"],
            "snapshot": pivot_b,
        },
        "rh_proved": False,
        "uniform_tail_certified": False,
    }
