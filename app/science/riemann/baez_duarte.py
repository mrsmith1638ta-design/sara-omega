from __future__ import annotations

import math
from typing import Iterable

from app.science.models import ProvenanceClass, ScienceAnalysis, ScienceCalculation
from .adversarial_gate import RHAdversarialGate
from .models import RHEquation, RHNumericalSnapshot, RHProofStatus, RiemannProofStatus, RiemannResult, RiemannRoute
from .vasyunin import (
    d_squared,
    determinant_ratio_d_squared,
    gram_matrix,
    optimal_coefficients,
    q_n,
    residual_against_negative_mobius,
    schur_extension,
    v_k,
    v_vector,
)


def mobius_sieve(n: int) -> list[int]:
    if n < 1:
        raise ValueError("n_must_be_positive")
    mu = [1] * (n + 1)
    is_prime = [True] * (n + 1)
    is_prime[:2] = [False, False]
    primes: list[int] = []
    mu[0] = 0
    for i in range(2, n + 1):
        if is_prime[i]:
            primes.append(i)
            mu[i] = -1
        for p in primes:
            if i * p > n:
                break
            is_prime[i * p] = False
            if i % p == 0:
                mu[i * p] = 0
                break
            mu[i * p] = -mu[i]
    return mu


def rho_n(n: int, x: float) -> float:
    if n < 1 or x <= 0.0:
        raise ValueError("rho_requires_positive_n_and_x")
    value = 1.0 / (n * x)
    return value - math.floor(value)


def selberg_coefficients(n: int) -> list[float]:
    if n < 2:
        raise ValueError("n_must_be_at_least_2")
    mu = mobius_sieve(n)
    log_n = math.log(n)
    return [0.0] + [
        -float(mu[k]) * (1.0 - math.log(k) / log_n)
        for k in range(1, n + 1)
    ]


def f_n(x: float, n: int) -> float:
    c = selberg_coefficients(n)
    return sum(c[k] * rho_n(k, x) for k in range(1, n + 1))


def e_n(x: float, n: int) -> float:
    if x <= 0.0:
        raise ValueError("x_must_be_positive")
    # Use the endpoint-inclusive representative chi_(0,1]. It differs from
    # chi_(0,1) only on a measure-zero set, so the L2 class is unchanged,
    # while the pointwise y=1 residual identity holds literally.
    chi = 1.0 if x <= 1.0 else 0.0
    return chi - f_n(x, n)


def theta_n(n: int) -> float:
    c = selberg_coefficients(n)
    log_n = math.log(n)
    return -log_n * sum(c[k] / k for k in range(1, n + 1))


def theta_n_mobius_form(n: int) -> float:
    mu = mobius_sieve(n)
    log_n = math.log(n)
    return (
        log_n * sum(mu[k] / k for k in range(1, n + 1))
        - sum(mu[k] * math.log(k) / k for k in range(1, n + 1))
    )


def psi_n(y: float, n: int) -> float:
    if y < 1.0:
        raise ValueError("y_must_be_at_least_1")
    mu = mobius_sieve(n)
    log_n = math.log(n)
    return (
        -log_n
        + log_n * sum(mu[k] * math.floor(y / k) for k in range(1, n + 1))
        - sum(mu[k] * math.log(k) * math.floor(y / k) for k in range(1, n + 1))
    )


def von_mangoldt_table(n: int) -> list[float]:
    if n < 1:
        raise ValueError("n_must_be_positive")
    table = [0.0] * (n + 1)
    sieve = [True] * (n + 1)
    sieve[:2] = [False, False]
    for p in range(2, n + 1):
        if not sieve[p]:
            continue
        multiple = p * p
        while multiple <= n:
            sieve[multiple] = False
            multiple += p
        power = p
        while power <= n:
            table[power] = math.log(p)
            if power > n // p:
                break
            power *= p
    return table


def chebyshev_psi(y: float) -> float:
    if y < 1.0:
        raise ValueError("y_must_be_at_least_1")
    m = math.floor(y)
    return sum(von_mangoldt_table(m))


def residual_identity(n: int, y: float) -> dict[str, float]:
    if y < 1.0:
        raise ValueError("y_must_be_at_least_1")
    lhs = e_n(1.0 / y, n)
    rhs = (theta_n(n) * y - psi_n(y, n)) / math.log(n)
    return {"lhs": lhs, "rhs": rhs, "absolute_error": abs(lhs - rhs)}


def finite_range_psi_identity(n: int, y: float) -> dict[str, float]:
    if not 1.0 <= y <= n:
        raise ValueError("finite_range_identity_requires_1_le_y_le_n")
    left = psi_n(y, n)
    right = chebyshev_psi(y)
    return {"psi_n": left, "chebyshev_psi": right, "absolute_error": abs(left - right)}


def _interval_integral(theta: float, constant: float, a: float, b: float) -> float:
    return (
        theta * theta * (b - a)
        - 2.0 * theta * constant * math.log(b / a)
        + constant * constant * (1.0 / a - 1.0 / b)
    )


def truncated_j_n(n: int, cutoff: int) -> float:
    """Exact integration on [1, cutoff] using psi_N's unit-interval constancy."""
    if n < 2 or cutoff <= 1:
        raise ValueError("truncated_j_requires_n_ge_2_and_cutoff_gt_1")
    theta = theta_n(n)
    total = 0.0
    for m in range(1, cutoff):
        constant = psi_n(float(m), n)
        total += _interval_integral(theta, constant, float(m), float(m + 1))
    return total


def finite_range_j_n(n: int) -> float:
    """Exact J_N contribution on [1,N], where psi_N(y)=Chebyshev psi(y)."""
    if n < 2:
        raise ValueError("finite_range_j_requires_n_ge_2")
    return truncated_j_n(n, n)


def tail_residual_sawtooth(n: int, y: float) -> float:
    """Exact identity for theta_N*y-psi_N(y) in fractional-part form."""
    if n < 2 or y < 1.0:
        raise ValueError("tail_residual_requires_n_ge_2_and_y_ge_1")
    mu = mobius_sieve(n)
    log_n = math.log(n)
    return log_n + sum(
        mu[k] * (log_n - math.log(k)) * ((y / k) - math.floor(y / k))
        for k in range(1, n + 1)
    )


def j_split_snapshot(n: int, cutoff: int) -> dict[str, float | bool]:
    """Auditable finite/tail decomposition with only a finite tail window computed."""
    if n < 2 or cutoff <= n:
        raise ValueError("j_split_requires_cutoff_gt_n_ge_2")
    finite = finite_range_j_n(n)
    through_cutoff = truncated_j_n(n, cutoff)
    return {
        "finite_range_1_to_N": finite,
        "tail_window_N_to_cutoff": through_cutoff - finite,
        "through_cutoff": through_cutoff,
        "tail_beyond_cutoff_uncomputed": True,
    }


def tail_attack_snapshot(n: int, cutoff: int, *, sample_count: int = 17) -> dict[str, object]:
    """Tail Attack I: finite-window tail evidence plus sawtooth diagnostics.

    This is intentionally evidence, not proof: the post-cutoff tail remains
    uncomputed and no asymptotic estimate is certified here.
    """
    if n < 2 or cutoff <= n:
        raise ValueError("tail_attack_requires_cutoff_gt_n_ge_2")
    if sample_count < 2:
        raise ValueError("sample_count_must_be_at_least_2")
    split = j_split_snapshot(n, cutoff)
    step = (cutoff - n) / (sample_count - 1)
    y_values = [float(n) + step * i for i in range(sample_count)]
    samples = [
        {"y": y, "theta_y_minus_psi_n": tail_residual_sawtooth(n, y)}
        for y in y_values
    ]
    values = [float(item["theta_y_minus_psi_n"]) for item in samples]
    mean = sum(values) / len(values)
    max_abs = max(abs(value) for value in values)
    rms = math.sqrt(sum(value * value for value in values) / len(values))
    log2 = math.log(n) ** 2
    tail_window = float(split["tail_window_N_to_cutoff"])
    return {
        "phase": "Tail Attack I",
        "proof_status": RHProofStatus.NUMERICAL_EVIDENCE.value,
        "N": n,
        "cutoff": cutoff,
        "finite_range_1_to_N": split["finite_range_1_to_N"],
        "tail_window_N_to_cutoff": tail_window,
        "tail_window_over_log_squared_N": tail_window / log2 if log2 else math.inf,
        "tail_beyond_cutoff_uncomputed": True,
        "sawtooth_identity": r"theta_N*y-psi_N(y)=log N+sum_{n<=N} mu(n)(log N-log n){y/n}",
        "sawtooth_samples": samples,
        "sawtooth_sample_mean": mean,
        "sawtooth_sample_max_abs": max_abs,
        "tail_window_rms": rms,
        "candidate_attack_lines": [
            "bound correlations among fractional-part functions {y/n}",
            "separate diagonal and off-diagonal averaging in the weighted sawtooth square",
            "test cancellation claims before promoting them to asymptotic lemmas",
        ],
        "limitations": [
            "finite tail window only",
            "tail beyond cutoff is not certified",
            "numerical cancellation cannot prove RH",
        ],
    }


def truncated_l2_identity(n: int, cutoff: int) -> dict[str, float | bool]:
    log_n = math.log(n)
    theta = theta_n(n)
    j = truncated_j_n(n, cutoff)
    return {
        "theta_term": theta * theta / (log_n * log_n),
        "truncated_integral_term": j / (log_n * log_n),
        "truncated_norm_squared": (theta * theta + j) / (log_n * log_n),
        "tail_uncomputed": True,
    }


def mellin_dirichlet_polynomial(coefficients: Iterable[float], s: complex) -> complex:
    values = list(coefficients)
    return sum(values[k - 1] * (k ** (-s)) for k in range(1, len(values) + 1))


def equation_registry() -> list[RHEquation]:
    return [
        RHEquation(
            equation_id="rh.rho_n",
            latex=r"\rho_n(x)=\left\{\frac{1}{nx}\right\}",
            description="Nyman-Beurling/Baez-Duarte integer-dilation basis.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["baez-duarte-2002"],
        ),
        RHEquation(
            equation_id="rh.gram",
            latex=r"G_{j,k}=\langle\rho_j,\rho_k\rangle=\int_0^\infty\rho_j(x)\rho_k(x)\,dx",
            description="Gram matrix of the integer-dilation basis.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["baez-duarte-2002", "vasyunin-gram"],
        ),
        RHEquation(
            equation_id="rh.v_k",
            latex=r"v_k=\langle\chi_{(0,1)},\rho_k\rangle=\frac{\log k+1-\gamma}{k}",
            description="Target-vector coordinate.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["nyman-beurling-gram-literature"],
        ),
        RHEquation(
            equation_id="rh.optimizer",
            latex=r"c_N=G_N^{-1}v_N",
            description="Finite-dimensional least-squares optimizer.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["linear-algebra"],
        ),
        RHEquation(
            equation_id="rh.distance",
            latex=r"d_N^2=1-v_N^T G_N^{-1}v_N",
            description="Squared best-approximation distance.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["baez-duarte-2002", "linear-algebra"],
        ),
        RHEquation(
            equation_id="rh.q_n",
            latex=r"Q_N(a)=d_N^2+(a-c_N)^T G_N(a-c_N)",
            description="Exact quadratic residual decomposition around the optimizer.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["linear-algebra"],
        ),
        RHEquation(
            equation_id="rh.mobius_residual",
            latex=r"r_N=v_N-G_N(-\mu),\qquad \delta_N=G_N^{-1}r_N",
            description="Mobius baseline residual and exact correction.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-derivation"],
        ),
        RHEquation(
            equation_id="rh.augmented_determinant",
            latex=r"\mathcal G_N=\begin{pmatrix}1&v_N^T\\v_N&G_N\end{pmatrix},\qquad d_N^2=\frac{\det\mathcal G_N}{\det G_N}",
            description="Augmented Gram determinant ratio.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["schur-complement"],
        ),
        RHEquation(
            equation_id="rh.schur_extension",
            latex=r"G_{N+1}=\begin{pmatrix}G_N&g_N\\g_N^T&a_N\end{pmatrix}",
            description="One-step Gram extension.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["linear-algebra"],
        ),
        RHEquation(
            equation_id="rh.schur_decrement",
            latex=r"s_N=a_N-g_N^TG_N^{-1}g_N>0,\quad t_N=b_N-g_N^TG_N^{-1}v_N,\quad d_{N+1}^2=d_N^2-\frac{t_N^2}{s_N}",
            description="Exact one-step Schur-complement distance decrement.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["schur-complement"],
        ),
        RHEquation(
            equation_id="rh.mellin",
            latex=r"\mathcal M\!\left[\chi-\sum_{k\le N}c_k\rho_k\right](s)=\frac{1+\zeta(s)A_N(s)}{s}",
            description="Corrected Mellin-sign identity with A_N(s)=sum c_k k^{-s}.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            dependencies=["Mellin transform in its valid strip"],
            source_ids=["internal-rh-sign-check", "nyman-beurling-mellin"],
        ),
        RHEquation(
            equation_id="rh.selberg_coefficients",
            latex=r"c_n=-\mu(n)\left(1-\frac{\log n}{\log N}\right)",
            description="Selberg-type Mobius coefficients used in the current constructive route.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["baez-duarte-family", "bettin-conrey-farmer-context"],
        ),
        RHEquation(
            equation_id="rh.constructive_residual",
            latex=r"F_N(x)=\sum_{n\le N}c_n\rho_n(x),\qquad e_N(x)=\chi_{(0,1)}(x)-F_N(x)",
            description="Constructive Selberg-candidate approximant and residual.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-algebra"],
        ),
        RHEquation(
            equation_id="rh.theta",
            latex=r"\theta_N=-\log N\sum_{n\le N}\frac{c_n}{n}=\log N\sum_{n\le N}\frac{\mu(n)}n-\sum_{n\le N}\frac{\mu(n)\log n}{n}",
            description="Theta normalization induced by the Selberg coefficients.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-algebra"],
        ),
        RHEquation(
            equation_id="rh.psi_n",
            latex=r"\psi_N(y)=-\log N+\log N\sum_{n\le N}\mu(n)\left\lfloor\frac yn\right\rfloor-\sum_{n\le N}\mu(n)\log n\left\lfloor\frac yn\right\rfloor",
            description="Finite Mobius-floor transform.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-algebra"],
        ),
        RHEquation(
            equation_id="rh.pointwise_residual",
            latex=r"e_N(1/y)=\frac{\theta_Ny-\psi_N(y)}{\log N}\qquad(y\ge1)",
            description="Exact residual identity for the Selberg coefficient candidate using the L2-equivalent endpoint-inclusive representative of chi.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-algebra"],
        ),
        RHEquation(
            equation_id="rh.mobius_divisor_identity",
            latex=r"\sum_{n\le y}\mu(n)\left\lfloor\frac yn\right\rfloor=1",
            description="Classical Möbius divisor identity used in the finite-range reduction.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["mobius-divisor-identities"],
        ),
        RHEquation(
            equation_id="rh.log_mobius_divisor_identity",
            latex=r"\sum_{n\le y}\mu(n)\log n\left\lfloor\frac yn\right\rfloor=-\psi(y)",
            description="Log-weighted Möbius divisor identity giving Chebyshev psi.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["mobius-divisor-identities"],
        ),
        RHEquation(
            equation_id="rh.finite_psi",
            latex=r"\psi_N(y)=\psi(y)\qquad(1\le y\le N)",
            description="Finite-range reduction to Chebyshev psi using divisor identities.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["mobius-divisor-identities"],
        ),
        RHEquation(
            equation_id="rh.finite_range_residual",
            latex=r"e_N(1/y)=\frac{\theta_Ny-\psi(y)}{\log N}\qquad(1\le y\le N)",
            description="Finite-range residual after replacing psi_N by Chebyshev psi.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-algebra", "mobius-divisor-identities"],
        ),
        RHEquation(
            equation_id="rh.l2_exact",
            latex=r"\|e_N\|_2^2=\frac{\theta_N^2}{\log^2N}+\frac1{\log^2N}\int_1^\infty|\theta_Ny-\psi_N(y)|^2\frac{dy}{y^2}",
            description="Exact L2 norm identity for the current Selberg-coefficient residual.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-change-of-variables"],
        ),
        RHEquation(
            equation_id="rh.j_n",
            latex=r"J_N=\int_1^\infty|\theta_Ny-\psi_N(y)|^2\frac{dy}{y^2}",
            description="Current analytic bottleneck quantity.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-reduction"],
        ),
        RHEquation(
            equation_id="rh.j_split",
            latex=r"J_N=\int_1^N|\theta_Ny-\psi(y)|^2\frac{dy}{y^2}+\int_N^\infty|\theta_Ny-\psi_N(y)|^2\frac{dy}{y^2}",
            description="Exact split of the bottleneck into the finite Chebyshev range and post-N tail.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-reduction", "mobius-divisor-identities"],
        ),
        RHEquation(
            equation_id="rh.tail_sawtooth",
            latex=r"\theta_Ny-\psi_N(y)=\log N+\sum_{n\le N}\mu(n)(\log N-\log n)\left\{\frac yn\right\}",
            description="Exact fractional-part representation useful for tail analysis.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-algebra"],
            notes=["This identity does not itself establish the required tail asymptotic."],
        ),
        RHEquation(
            equation_id="rh.tail_attack_i",
            latex=r"\int_N^X|\theta_Ny-\psi_N(y)|^2\frac{dy}{y^2}\quad\text{with}\quad\theta_Ny-\psi_N(y)=\log N+\sum_{n\le N}\mu(n)(\log N-\log n)\{y/n\}",
            description="Tail Attack I finite-window tail diagnostic and sawtooth red-team object.",
            proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
            source_ids=["internal-rh-tail-attack"],
            notes=[
                "This computes controlled evidence for the y>N tail.",
                "It does not prove the required asymptotic tail bound.",
            ],
        ),
        RHEquation(
            equation_id="rh.stronger_finite_target",
            latex=r"\int_1^N|\psi(y)-\theta_Ny|^2\frac{dy}{y^2}=O(\log N)",
            description="Earlier stronger finite-range target; useful if proved but stronger than required.",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
            dependencies=["unconditional proof of the displayed estimate"],
            source_ids=["internal-rh-reduction"],
            notes=["The current sufficient target only requires J_N=o(log^2 N)."],
        ),
        RHEquation(
            equation_id="rh.sufficient_target",
            latex=r"\theta_N=O(1)\quad\text{and}\quad J_N=o(\log^2N)",
            description="Sufficient target for this constructive route to force ||e_N||_2 to zero.",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
            dependencies=["unconditional proof of both asymptotic statements"],
            source_ids=["internal-rh-reduction"],
            notes=["This target is not currently proved by the engine."],
        ),
        RHEquation(
            equation_id="rh.sufficient_implication_chain",
            latex=r"\theta_N=O(1),\ J_N=o(\log^2N)\Longrightarrow\|e_N\|_2^2\to0\Longrightarrow d_N\to0\Longrightarrow RH",
            description="Conditional implication chain from the current asymptotic target to RH.",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
            dependencies=["theta_N=O(1)", "J_N=o(log^2 N)", "Baez-Duarte criterion"],
            source_ids=["internal-rh-reduction", "baez-duarte-2002"],
            notes=["The chain is conditional because its two asymptotic hypotheses are not certified."],
        ),
        RHEquation(
            equation_id="rh.baez_duarte_limit",
            latex=r"RH\iff d_N\to0",
            description="Baez-Duarte integer-dilation criterion.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["baez-duarte-2002"],
        ),
    ]


def numerical_snapshot(n: int = 8, cutoff: int = 64) -> RHNumericalSnapshot:
    if n < 2:
        raise ValueError("snapshot_n_must_be_at_least_2")
    schur = schur_extension(n)
    return RHNumericalSnapshot(
        n=n,
        d_squared=d_squared(n),
        theta_n=theta_n(n),
        truncated_j_n=truncated_j_n(n, cutoff),
        j_cutoff=cutoff,
        schur_next_d_squared=schur["recursive_next_d_squared"],
        direct_next_d_squared=schur["direct_next_d_squared"],
        metadata={
            "tail_uncomputed": True,
            "determinant_ratio_d_squared": determinant_ratio_d_squared(n),
            "schur_absolute_error": schur["absolute_error"],
            "finite_N_cannot_certify_RH": True,
        },
    )


class RiemannResearchEngine:
    domain = "riemann_hypothesis"

    def analyze_text(self, text: str) -> ScienceAnalysis:
        equations = equation_registry()
        snapshot = numerical_snapshot()
        gate = RHAdversarialGate()
        calculations: list[ScienceCalculation] = []

        for equation in equations:
            if equation.proof_status == RHProofStatus.CONJECTURAL_LEMMA:
                provenance = ProvenanceClass.CONJECTURAL_MATHEMATICS
                evidence_status = "UNVERIFIED"
            else:
                provenance = ProvenanceClass.ESTABLISHED_MATHEMATICS
                evidence_status = "SUPPORTED"
            calculations.append(
                ScienceCalculation(
                    equation_id=equation.equation_id,
                    result={
                        "latex": equation.latex,
                        "description": equation.description,
                        "proof_status": equation.proof_status.value,
                        "dependencies": equation.dependencies,
                        "notes": equation.notes,
                    },
                    provenance_class=provenance,
                    evidence_status=evidence_status,
                    assumptions=list(equation.dependencies),
                    limitations=(
                        ["Symbolic identity does not by itself prove the required N-to-infinity limit."]
                        if equation.proof_status == RHProofStatus.SYMBOLIC_IDENTITY
                        else ["Unproved asymptotic target; cannot be promoted to theorem."]
                    ),
                    source_ids=list(equation.source_ids),
                    validation_status=(
                        "SYMBOLIC_IDENTITY"
                        if equation.proof_status == RHProofStatus.SYMBOLIC_IDENTITY
                        else "CONJECTURAL_LEMMA"
                    ),
                )
            )

        calculations.append(
            ScienceCalculation(
                equation_id="rh.numerical_snapshot",
                inputs={"N": snapshot.n, "J_cutoff": snapshot.j_cutoff},
                result=snapshot.model_dump(mode="json"),
                provenance_class=ProvenanceClass.NUMERICAL_MATHEMATICS,
                evidence_status="SUPPORTED",
                assumptions=["finite precision arithmetic", "finite N", "J_N integral truncated at configured cutoff"],
                limitations=["No finite-N computation can establish RH.", "The J_N tail beyond the cutoff is not certified."],
                source_ids=["sara-rh-numerical-runner"],
                validation_status="NUMERICAL_EVIDENCE",
            )
        )

        false_promotion = gate.evaluate(
            claim="RH proved",
            proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
            finite_n_only=True,
        )
        tail_attack = tail_attack_snapshot(8, 64)
        tail_red_team = gate.evaluate_tail_bound_claim(
            "Assume square-root cancellation in the fractional-part sawtooth tail.",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
        )
        calculations.append(
            ScienceCalculation(
                equation_id="rh.tail_attack_i_snapshot",
                inputs={"N": tail_attack["N"], "cutoff": tail_attack["cutoff"]},
                result=tail_attack,
                provenance_class=ProvenanceClass.NUMERICAL_MATHEMATICS,
                evidence_status="SUPPORTED",
                assumptions=["finite N", "finite cutoff", "sawtooth identity evaluated on a sample grid"],
                limitations=[
                    "Tail Attack I is finite-window evidence only.",
                    "The tail beyond cutoff remains uncomputed.",
                    "Cancellation hypotheses require independent proof.",
                ],
                source_ids=["internal-rh-tail-attack"],
                validation_status="NUMERICAL_EVIDENCE",
            )
        )
        return ScienceAnalysis(
            domain=self.domain,
            summary=(
                "Governed Nyman-Beurling/Baez-Duarte RH research engine with symbolic identities, "
                "finite numerical evidence, Schur/Gram diagnostics, and fail-closed proof promotion."
            ),
            calculations=calculations,
            evidence_gaps=[
                "No unconditional proof of theta_N=O(1) is attached.",
                "No unconditional proof of J_N=o(log^2 N) is attached.",
                "No formal certificate establishes the N-to-infinity step required for RH.",
            ],
            confidence=0.95,
            execution_authority=False,
            metadata={
                "rh_status": "UNSOLVED",
                "proof_status": RHProofStatus.CONJECTURAL_LEMMA.value,
                "formal_proof_certified": False,
                "equation_count": len(equations),
                "proof_promotion_gate": {
                    "false_promotion_allowed": false_promotion.allowed,
                    "status": false_promotion.status,
                    "reasons": false_promotion.reasons,
                },
                "current_bottleneck": "J_N=o(log^2 N) together with theta_N=O(1)",
                "bottleneck_split": "J_N = finite Chebyshev range [1,N] + post-N psi_N tail",
                "tail_attack_i": tail_attack,
                "tail_bound_red_team": {
                    "sqrt_cancellation_allowed": tail_red_team.allowed,
                    "status": tail_red_team.status,
                    "reasons": tail_red_team.reasons,
                },
                "conversation_cross_reference_complete": True,
                "numerical_snapshot": snapshot.model_dump(mode="json"),
            },
        )


def riemann_sufficient_target() -> RiemannRoute:
    return RiemannRoute(
        statement=(
            "theta_N = O(1) and J_N = o(log^2 N) would force ||e_N||_2 -> 0 "
            "and hence RH through the Baez-Duarte/Nyman-Beurling criterion."
        ),
        status=RiemannProofStatus.CANDIDATE_LEMMA,
        evidence=["Baez-Duarte/Nyman-Beurling equivalence route", "SARA V3.4.0 RH engine spec"],
        limitations=["This is an RH-equivalent proof target, not an unconditional proof."],
    )


def error_norm_identity_record(N: int) -> RiemannResult:
    return RiemannResult(
        statement=(
            f"For N={N}, the tracked symbolic form is ||e_N||_2^2 = "
            "theta_N^2 / log^2(N) + J_N / log^2(N)."
        ),
        status=RiemannProofStatus.SYMBOLIC_IDENTITY,
        evidence=["Selberg coefficient transform identity"],
        limitations=["The identity does not prove that J_N = o(log^2 N)."],
        metadata={"N": N},
    )


def split_J_target(N: int) -> RiemannResult:
    return RiemannResult(
        statement=(
            f"J_N for N={N} is split into a finite range 1 <= y <= N and a tail y > N; "
            "the finite range uses psi_N(y)=psi(y), while the tail remains separately bounded."
        ),
        status=RiemannProofStatus.SYMBOLIC_IDENTITY,
        evidence=["Classical divisor identities for y <= N"],
        limitations=["No unconditional asymptotic tail bound is certified by this record."],
        metadata={"N": N, "split": ["finite", "tail"]},
    )
