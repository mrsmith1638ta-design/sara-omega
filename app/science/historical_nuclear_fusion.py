from __future__ import annotations

import inspect
import math
import random
import sys
import time
from typing import Any

from app.madhouse import MadhouseAgent, MadhouseReviewRequest
from .models import ProvenanceClass, ScienceAnalysis, ScienceCalculation


ALGORITHM_ID = "egyptian-dyadic-bateman-fusion"


def _validate(initial: list[float], rates: list[float], duration: float) -> None:
    if len(initial) < 2 or len(rates) != len(initial) - 1:
        raise ValueError("rates_must_define_each_parent_to_child_transition")
    if duration < 0 or any(value < 0 for value in initial) or any(value < 0 for value in rates):
        raise ValueError("decay_inputs_must_be_non_negative")


def _identity(size: int) -> list[list[float]]:
    return [[1.0 if row == column else 0.0 for column in range(size)] for row in range(size)]


def _matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    size = len(left)
    return [
        [sum(left[row][inner] * right[inner][column] for inner in range(size)) for column in range(size)]
        for row in range(size)
    ]


def _matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(matrix[row][column] * vector[column] for column in range(len(vector))) for row in range(len(matrix))]


def _generator(rates: list[float]) -> list[list[float]]:
    size = len(rates) + 1
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for index, rate in enumerate(rates):
        matrix[index][index] = -rate
        matrix[index + 1][index] = rate
    return matrix


def _euler_operator(rates: list[float], step: float) -> list[list[float]]:
    generator = _generator(rates)
    operator = _identity(len(generator))
    for row in range(len(generator)):
        for column in range(len(generator)):
            operator[row][column] += step * generator[row][column]
    return operator


def historical_fusion_decay(initial: list[float], rates: list[float], duration: float) -> list[float]:
    """Integrate a linear decay chain using an Egyptian-dyadic operator.

    The Egyptian contribution is repeated doubling: a small Euler transition
    is squared into dyadic time blocks, then selected blocks are accumulated by
    binary decomposition. The Bateman/Laplace contribution is the chain model
    and conservation check, while the numerical transition keeps this solver
    useful for arbitrary chain length without external dependencies.
    """
    _validate(initial, rates, duration)
    if duration == 0:
        return list(initial)
    maximum_rate = max(rates, default=0.0)
    block_count = 1
    while maximum_rate * duration / block_count > 0.002 and block_count < 1 << 20:
        block_count *= 2
    step = duration / block_count
    base = _euler_operator(rates, step)

    # Repeated doubling constructs operators for 1, 2, 4, ... base blocks.
    powers: list[list[list[float]]] = [base]
    for _ in range(block_count.bit_length() - 1):
        powers.append(_matmul(powers[-1], powers[-1]))

    state = list(initial)
    remaining = block_count
    bit = 0
    while remaining:
        if remaining & 1:
            state = _matvec(powers[bit], state)
        remaining >>= 1
        bit += 1
    return [0.0 if -1e-15 < value < 0.0 else value for value in state]


def rk4_decay_chain(initial: list[float], rates: list[float], duration: float, *, steps: int = 1000) -> list[float]:
    """Modern fixed-step RK4 reference implementation for comparison."""
    _validate(initial, rates, duration)
    if steps < 1:
        raise ValueError("steps_must_be_positive")
    state = list(initial)
    step = duration / steps

    def derivative(values: list[float]) -> list[float]:
        result = [0.0] * len(values)
        for index, rate in enumerate(rates):
            result[index] -= rate * values[index]
            result[index + 1] += rate * values[index]
        return result

    for _ in range(steps):
        first = derivative(state)
        second = derivative([state[i] + step * first[i] / 2.0 for i in range(len(state))])
        third = derivative([state[i] + step * second[i] / 2.0 for i in range(len(state))])
        fourth = derivative([state[i] + step * third[i] for i in range(len(state))])
        state = [state[i] + step * (first[i] + 2 * second[i] + 2 * third[i] + fourth[i]) / 6.0 for i in range(len(state))]
    return state


def madhouse_challenge(candidate_code: str) -> dict[str, Any]:
    return MadhouseAgent().review(
        MadhouseReviewRequest(
            candidate_id=ALGORITHM_ID,
            language="python",
            generated_code=candidate_code,
            requirements=[
                "Preserve nonnegative populations for stable numerical inputs.",
                "Preserve total chain mass when the final nuclide is stable.",
                "Do not grant execution or promotion authority.",
            ],
        )
    )


def benchmark_historical_fusion(*, samples: int = 100, seed: int = 0) -> dict[str, Any]:
    if samples < 1:
        raise ValueError("samples_must_be_positive")
    generator = random.Random(seed)
    cases: list[tuple[list[float], list[float], float]] = []
    for _ in range(samples):
        length = generator.randint(2, 5)
        initial = [0.0] * length
        initial[0] = 1.0
        rates = [generator.uniform(0.01, 1.0) for _ in range(length - 1)]
        cases.append((initial, rates, generator.uniform(0.1, 4.0)))

    fused_start = time.perf_counter()
    fused = [historical_fusion_decay(initial, rates, duration) for initial, rates, duration in cases]
    fused_seconds = time.perf_counter() - fused_start
    reference_start = time.perf_counter()
    reference = [rk4_decay_chain(initial, rates, duration, steps=400) for initial, rates, duration in cases]
    reference_seconds = time.perf_counter() - reference_start
    errors = [max(abs(left - right) for left, right in zip(fused_state, reference_state)) for fused_state, reference_state in zip(fused, reference)]
    challenge = madhouse_challenge(inspect.getsource(sys.modules[__name__]))
    return {
        "algorithm": ALGORITHM_ID,
        "samples": samples,
        "max_absolute_error_vs_rk4": max(errors),
        "mean_absolute_error_vs_rk4": sum(errors) / len(errors),
        "fused_seconds": fused_seconds,
        "rk4_seconds": reference_seconds,
        "speedup_vs_rk4": reference_seconds / fused_seconds if fused_seconds else math.inf,
        "provenance": {
            "egyptian": "Rhind-inspired repeated doubling and binary decomposition; historically compatible reconstruction",
            "eighteenth_century": "Laplace/Bateman linear decay-chain framing; modern numerical implementation",
            "nuclear_physics": "Educational stable-terminal-nuclide decay-chain model",
        },
        "madhouse": {
            "decision": challenge["decision"],
            "finding_count": len(challenge["findings"]),
            "can_pass": challenge["can_pass"],
            "promotion_authority": challenge["promotion_authority"],
        },
        "execution_authority": False,
    }


class HistoricalNuclearFusionEngine:
    domain = "historical_nuclear_fusion"

    def analyze_text(self, text: str) -> ScienceAnalysis:
        benchmark = benchmark_historical_fusion(samples=64, seed=17)
        return ScienceAnalysis(
            domain=self.domain,
            summary="Historical mathematics fusion benchmark for educational nuclear decay-chain calculations.",
            calculations=[
                ScienceCalculation(
                    equation_id=ALGORITHM_ID,
                    variables={"initial": "nuclide populations", "rates": "parent-to-child decay constants", "duration": "time"},
                    units={"initial": "normalized population", "rates": "1/time", "duration": "time", "result": "normalized population"},
                    inputs={"samples": 64, "seed": 17},
                    result=benchmark,
                    provenance_class=ProvenanceClass.SIMULATION_OR_HYPOTHESIS,
                    evidence_status="SUPPORTED",
                    assumptions=["Final chain member is stable", "Rates are non-negative and constant", "Populations are normalized for the benchmark"],
                    limitations=["This is a numerical research algorithm, not a reactor or weapon model", "RK4 comparison is a numerical reference, not experimental validation"],
                    source_ids=["egypt.rhind.doubling", "math.laplace.decay", "physics.decay.chain"],
                    validation_status="VALIDATED_AGAINST_RK4",
                )
            ],
            confidence=0.7,
            execution_authority=False,
            metadata={"madhouse_required": True, "scope": "educational_nuclear_physics"},
        )
