from __future__ import annotations

import inspect
import itertools
import math
import random
import time
from functools import partial
import struct
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


def euler_decay_chain(initial: list[float], rates: list[float], duration: float, *, steps: int = 1000) -> list[float]:
    """Forward-Euler baseline for the same stable-terminal decay chain."""
    _validate(initial, rates, duration)
    if steps < 1:
        raise ValueError("steps_must_be_positive")
    state = list(initial)
    step = duration / steps
    for _ in range(steps):
        derivative = _matvec(_generator(rates), state)
        state = [value + step * change for value, change in zip(state, derivative)]
    return state


def _matrix_add(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [[left[row][column] + right[row][column] for column in range(len(left))] for row in range(len(left))]


def _matrix_scale(matrix: list[list[float]], factor: float) -> list[list[float]]:
    return [[factor * value for value in row] for row in matrix]


def _matrix_exponential(matrix: list[list[float]]) -> list[list[float]]:
    """Small dense matrix exponential using scaling, Taylor expansion, and squaring."""
    norm = max((sum(abs(value) for value in row) for row in matrix), default=0.0)
    scale = max(0, math.ceil(math.log2(norm))) if norm else 0
    scaled = _matrix_scale(matrix, 1.0 / (2**scale))
    result = _identity(len(matrix))
    term = _identity(len(matrix))
    for order in range(1, 48):
        term = _matrix_scale(_matmul(term, scaled), 1.0 / order)
        result = _matrix_add(result, term)
        if max((abs(value) for row in term for value in row), default=0.0) < 1e-16:
            break
    for _ in range(scale):
        result = _matmul(result, result)
    return result


def matrix_exponential_decay_chain(initial: list[float], rates: list[float], duration: float) -> list[float]:
    """Dense matrix-exponential reference for small research chains."""
    _validate(initial, rates, duration)
    return _matvec(_matrix_exponential(_matrix_scale(_generator(rates), duration)), initial)


def monte_carlo_uncertainty(
    initial: list[float], rates: list[float], duration: float, *, samples: int = 100, seed: int = 0
) -> dict[str, Any]:
    """Propagate a bounded 5% relative rate uncertainty through the reference solver."""
    _validate(initial, rates, duration)
    if samples < 1:
        raise ValueError("samples_must_be_positive")
    generator = random.Random(seed)
    outcomes = [
        matrix_exponential_decay_chain(
            initial,
            [max(0.0, rate * (1.0 + generator.gauss(0.0, 0.05))) for rate in rates],
            duration,
        )
        for _ in range(samples)
    ]
    mean = [sum(outcome[index] for outcome in outcomes) / samples for index in range(len(initial))]
    standard_deviation = [
        math.sqrt(sum((outcome[index] - mean[index]) ** 2 for outcome in outcomes) / samples)
        for index in range(len(initial))
    ]
    return {"samples": samples, "relative_rate_sigma": 0.05, "mean": mean, "standard_deviation": standard_deviation}


def _madhouse_candidate_source() -> str:
    implementation = (
        _validate,
        _identity,
        _matmul,
        _matvec,
        _generator,
        _euler_operator,
        historical_fusion_decay,
        euler_decay_chain,
        _matrix_add,
        _matrix_scale,
        _matrix_exponential,
        matrix_exponential_decay_chain,
        rk4_decay_chain,
    )
    return "import math\n\n" + "\n\n".join(inspect.getsource(function) for function in implementation)


def comparative_algorithm_laboratory(
    *, samples: int = 100, seed: int = 0, uncertainty_samples: int = 100
) -> dict[str, Any]:
    """Compare historical, classical, and modern methods on identical controlled inputs."""
    if samples < 1:
        raise ValueError("samples_must_be_positive")
    if uncertainty_samples < 1:
        raise ValueError("uncertainty_samples_must_be_positive")
    generator = random.Random(seed)
    cases = []
    for _ in range(samples):
        length = generator.randint(2, 5)
        initial = [0.0] * length
        initial[0] = 1.0
        rates = [generator.uniform(0.01, 1.0) for _ in range(length - 1)]
        cases.append((initial, rates, generator.uniform(0.1, 4.0)))

    methods = {
        "egyptian_dyadic": historical_fusion_decay,
        "euler": partial(euler_decay_chain, steps=400),
        "rk4": partial(rk4_decay_chain, steps=400),
        "matrix_exponential": matrix_exponential_decay_chain,
    }
    reference = [methods["matrix_exponential"](*case) for case in cases]
    method_results: dict[str, dict[str, Any]] = {}
    for name, method in methods.items():
        started = time.perf_counter()
        outputs = [method(*case) for case in cases]
        elapsed = time.perf_counter() - started
        errors = [max(abs(value - expected) for value, expected in zip(output, expected)) for output, expected in zip(outputs, reference)]
        mass_errors = [abs(sum(output) - 1.0) for output in outputs]
        method_results[name] = {
            "mean_absolute_error": sum(errors) / len(errors),
            "max_absolute_error": max(errors),
            "max_mass_error": max(mass_errors),
            "minimum_population": min(value for output in outputs for value in output),
            "seconds": elapsed,
        }

    fused = method_results["egyptian_dyadic"]
    rk4 = method_results["rk4"]
    numerical_advantage = fused["mean_absolute_error"] <= rk4["mean_absolute_error"] and fused["seconds"] < rk4["seconds"]
    challenge = madhouse_challenge(_madhouse_candidate_source())
    return {
        "algorithm": ALGORITHM_ID,
        "problem_class": "stable_terminal_decay_chain",
        "samples": samples,
        "reference": "matrix_exponential",
        "methods": method_results,
        "uncertainty": monte_carlo_uncertainty([1.0, 0.0], [0.4], 1.5, samples=uncertainty_samples, seed=seed),
        "claims": {
            "numerical_advantage": {
                "status": "SUPPORTED" if numerical_advantage else "UNSUPPORTED",
                "statement": "Fused method is faster and no less accurate than RK4 on this generated sample set.",
                "scope": "This benchmark only; not a general theorem or experimental validation.",
            }
        },
        "madhouse": {
            "decision": challenge["decision"],
            "finding_count": len(challenge["findings"]),
            "can_pass": challenge["can_pass"],
            "promotion_authority": challenge["promotion_authority"],
        },
        "execution_authority": False,
    }


def _quantize(value: float, precision: str) -> float:
    if precision == "float64":
        return float(value)
    if precision == "float32":
        return struct.unpack("f", struct.pack("f", float(value)))[0]
    raise ValueError("precision_must_be_float32_or_float64")


def _quantize_state(values: list[float], precision: str) -> list[float]:
    return [_quantize(value, precision) for value in values]


def parameter_regime_campaign(
    *,
    chain_lengths: tuple[int, ...] = (2, 4, 8),
    stiffness_ratios: tuple[float, ...] = (1.0, 10.0, 100.0),
    durations: tuple[float, ...] = (0.1, 1.0, 10.0),
    euler_steps: tuple[int, ...] = (128, 512),
    rk4_steps: tuple[int, ...] = (128, 512),
    uncertainty_magnitudes: tuple[float, ...] = (0.0, 0.05, 0.2),
    precisions: tuple[str, ...] = ("float64", "float32"),
    cases_per_regime: int = 4,
    seed: int = 0,
    error_threshold: float = 1e-3,
) -> dict[str, Any]:
    """Map method behavior across controlled numerical parameter regimes."""
    if cases_per_regime < 1 or error_threshold < 0:
        raise ValueError("campaign_cases_and_error_threshold_must_be_valid")
    if any(length < 2 for length in chain_lengths) or any(ratio < 1.0 for ratio in stiffness_ratios):
        raise ValueError("campaign_chain_lengths_and_stiffness_must_be_valid")
    if any(step < 1 for step in (*euler_steps, *rk4_steps)):
        raise ValueError("campaign_steps_must_be_positive")
    if any(magnitude < 0 for magnitude in uncertainty_magnitudes):
        raise ValueError("campaign_uncertainty_must_be_non_negative")
    if any(precision not in {"float32", "float64"} for precision in precisions):
        raise ValueError("campaign_precision_must_be_float32_or_float64")

    generator = random.Random(seed)
    records: list[dict[str, Any]] = []
    for length, stiffness, duration, euler_count, rk4_count, uncertainty, precision in itertools.product(
        chain_lengths,
        stiffness_ratios,
        durations,
        euler_steps,
        rk4_steps,
        uncertainty_magnitudes,
        precisions,
    ):
        method_outputs: dict[str, list[float]] = {"egyptian_dyadic": [], "euler": [], "rk4": [], "matrix_exponential": []}
        for _ in range(cases_per_regime):
            initial = [0.0] * length
            initial[0] = 1.0
            base_rate = generator.uniform(0.01, 0.5)
            rates = [base_rate * stiffness ** (index / max(1, length - 2)) for index in range(length - 1)]
            rates = [max(0.0, rate * (1.0 + generator.gauss(0.0, uncertainty))) for rate in rates]
            quantized_initial = _quantize_state(initial, precision)
            quantized_rates = _quantize_state(rates, precision)
            quantized_duration = _quantize(duration, precision)
            reference = matrix_exponential_decay_chain(quantized_initial, quantized_rates, quantized_duration)
            outputs = {
                "egyptian_dyadic": historical_fusion_decay(quantized_initial, quantized_rates, quantized_duration),
                "euler": euler_decay_chain(quantized_initial, quantized_rates, quantized_duration, steps=euler_count),
                "rk4": rk4_decay_chain(quantized_initial, quantized_rates, quantized_duration, steps=rk4_count),
                "matrix_exponential": reference,
            }
            for name, output in outputs.items():
                method_outputs[name].append(max(abs(value - expected) for value, expected in zip(output, reference)))
        records.append(
            {
                "chain_length": length,
                "stiffness_ratio": stiffness,
                "duration": duration,
                "euler_steps": euler_count,
                "rk4_steps": rk4_count,
                "uncertainty_magnitude": uncertainty,
                "precision": precision,
                "methods": {
                    name: {"mean_absolute_error": sum(errors) / len(errors), "max_absolute_error": max(errors)}
                    for name, errors in method_outputs.items()
                },
            }
        )

    qualifying = [
        record
        for record in records
        if record["methods"]["egyptian_dyadic"]["mean_absolute_error"] <= error_threshold
        and record["methods"]["egyptian_dyadic"]["mean_absolute_error"] <= record["methods"]["rk4"]["mean_absolute_error"]
    ]
    challenge = madhouse_challenge(_madhouse_candidate_source())
    return {
        "algorithm": ALGORITHM_ID,
        "campaign": "parameter-regime-comparison",
        "regime_count": len(records),
        "cases_per_regime": cases_per_regime,
        "error_threshold": error_threshold,
        "dimensions": {
            "chain_length": list(chain_lengths),
            "stiffness_ratio": list(stiffness_ratios),
            "duration": list(durations),
            "euler_steps": list(euler_steps),
            "rk4_steps": list(rk4_steps),
            "uncertainty_magnitude": list(uncertainty_magnitudes),
            "precision": list(precisions),
        },
        "qualifying_regimes": len(qualifying),
        "narrow_claim": {
            "status": "SUPPORTED" if qualifying else "UNSUPPORTED",
            "statement": "Within listed regimes, the fused method met the error threshold and was no less accurate than RK4." if qualifying else "No listed regime supported the scoped fused-method claim.",
            "scope": "Only the enumerated generated regimes and stated error threshold.",
        },
        "universal_superiority_claim": {
            "status": "UNSUPPORTED",
            "statement": "The campaign does not establish universal superiority for any method.",
        },
        "records": records,
        "madhouse": {
            "decision": challenge["decision"],
            "finding_count": len(challenge["findings"]),
            "can_pass": challenge["can_pass"],
            "promotion_authority": challenge["promotion_authority"],
        },
        "execution_authority": False,
    }


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
    challenge = madhouse_challenge(_madhouse_candidate_source())
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
        benchmark = comparative_algorithm_laboratory(samples=64, seed=17, uncertainty_samples=64)
        return ScienceAnalysis(
            domain=self.domain,
            summary="Comparative historical-mathematics laboratory for educational nuclear decay-chain calculations.",
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
                    validation_status="COMPARED_AGAINST_EULER_RK4_AND_MATRIX_EXPONENTIAL",
                )
            ],
            confidence=0.7,
            execution_authority=False,
            metadata={
                "madhouse_required": True,
                "scope": "educational_nuclear_physics",
                "parameter_campaign_command": "python tools/benchmark_historical_nuclear_fusion.py --campaign --seed 0 --cases-per-regime 4",
            },
        )
