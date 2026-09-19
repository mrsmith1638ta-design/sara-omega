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
            equation_id="rh.tail_periodicity",
            latex=r"R_N(y+L_N)=R_N(y),\qquad R_N(y)=\theta_Ny-\psi_N(y),\quad L_N=\operatorname{lcm}(1,\ldots,N)",
            description="Exact periodicity of the fixed-N tail residual induced by the fractional-part representation.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-i"],
            notes=["The period grows rapidly with N and does not by itself imply the required asymptotic tail bound."],
        ),
        RHEquation(
            equation_id="rh.tail_period_mean_square",
            latex=r"M_N=\left(\log N+\frac12\sum_{n\le N}a_n\right)^2+\frac1{12}\sum_{m,n\le N}a_ma_n\frac{\gcd(m,n)^2}{mn},\quad a_n=\mu(n)(\log N-\log n)",
            description="Exact full-period mean square of the fixed-N residual using centered periodic Bernoulli/sawtooth covariance.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-i", "periodic-bernoulli-covariance"],
            notes=["A full-period mean square is a structural identity, not a uniform estimate for the tail beginning at y=N."],
        ),
        RHEquation(
            equation_id="rh.tail_covariance_jordan",
            latex=r"C_N=\frac1{12}\sum_{d\le N}J_2(d)\left(\sum_{d\mid m\le N}\frac{a_m}{m}\right)^2",
            description="Exact Jordan-totient sum-of-squares decomposition of the gcd covariance term.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-ii", "jordan-totient-divisor-identity"],
            notes=["The decomposition is positive semidefinite; there is no cancellation between divisor layers."],
        ),
        RHEquation(
            equation_id="rh.tail_covariance_squarefree_layers",
            latex=r"C_N=\frac1{12}\sum_{\substack{d\le N\\\mu(d)^2=1}}\frac{J_2(d)}{d^2}\left(\sum_{\substack{k\le N/d\\(k,d)=1}}\frac{\mu(k)\log((N/d)/k)}{k}\right)^2",
            description="Equivalent squarefree/coprime Möbius-layer decomposition of the covariance.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-ii"],
            notes=["All arithmetic cancellation is localized inside the coprime Möbius layer sums."],
        ),
        RHEquation(
            equation_id="rh.tail_covariance_linear_bound",
            latex=r"C_N\le K N,\qquad K=\frac{12(\log2)^2+104(\log2)^3+300(\log2)^4}{12}<9.14",
            description="Unconditional uniform linear bound from harmonic domination and dyadic summation.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-ii-proof"],
            notes=["This controls the covariance component only; it does not by itself prove T_N=o(log^2 N)."],
        ),
        RHEquation(
            equation_id="rh.tail_energy_transfer",
            latex=r"A_N(x)\le M_N(x-N)+D_N\ \forall x\ge N\Longrightarrow T_N\le\frac{M_N}{N}+\frac{D_N}{N^2}",
            description="Conditional integration-by-parts transfer from cumulative unweighted tail energy to the weighted tail.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            dependencies=["a proved uniform cumulative-energy discrepancy bound D_N"],
            source_ids=["internal-rh-tail-attack-ii-calculus"],
            notes=["The implication is elementary; the required uniform discrepancy estimate is not yet proved."],
        ),
        RHEquation(
            equation_id="rh.tail_attack_ii_target",
            latex=r"C_N=O(N)\ \text{is proved; remaining: control mean component and }D_N\text{ strongly enough to force }T_N=o(\log^2N)",
            description="Tail Attack II research target after isolating and bounding the gcd covariance component.",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
            dependencies=["uniform mean-component control", "uniform cumulative-energy discrepancy control", "valid period-to-tail transfer"],
            source_ids=["internal-rh-tail-attack-ii"],
            notes=["No RH or Möbius-randomness assumption may be used to fill the remaining gaps."],
        ),
        RHEquation(
            equation_id="rh.tail_centered_decomposition",
            latex=r"R_N(y)=A_N+S_N(y),\quad A_N=\log N+\frac12\sum_{n\le N}\mu(n)(\log N-\log n),\quad S_N(y)=\sum_{n\le N}a_n\left(\left\{\frac yn\right\}-\frac12\right)",
            description="Exact decomposition into the period mean component and centered sawtooth residual.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iii"],
        ),
        RHEquation(
            equation_id="rh.tail_mean_mertens",
            latex=r"A_N=\log N+\frac12\int_1^N\frac{M(t)}{t}\,dt,\qquad M(t)=\sum_{n\le t}\mu(n)",
            description="Exact partial-summation form exposing the Möbius summatory quantity governing the mean component.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iii-partial-summation"],
            notes=["This identity does not assume a cancellation rate for M(t)."],
        ),
        RHEquation(
            equation_id="rh.tail_period_energy_components",
            latex=r"M_N=A_N^2+C_N",
            description="Exact period-energy decomposition into mean contribution and centered covariance.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iii"],
        ),
        RHEquation(
            equation_id="rh.tail_discrepancy",
            latex=r"E_N(x)=\int_N^xR_N(y)^2\,dy-M_N(x-N),\qquad D_N=\sup_{x\ge N}|E_N(x)|",
            description="Cumulative-energy discrepancy relative to the exact full-period mean.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iii"],
            notes=["For fixed N, E_N is periodic with period lcm(1,...,N)."],
        ),
        RHEquation(
            equation_id="rh.tail_transfer_exact",
            latex=r"T_N=\frac{M_N}{N}+2\int_N^\infty\frac{E_N(y)}{y^3}\,dy",
            description="Exact integration-by-parts transfer from cumulative period-energy discrepancy to the weighted tail.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iii-calculus"],
        ),
        RHEquation(
            equation_id="rh.tail_transfer_error",
            latex=r"\left|T_N-\frac{M_N}{N}\right|\le\frac{D_N}{N^2}",
            description="Exact fixed-N transfer error bound obtained from the discrepancy supremum.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iii-calculus"],
            notes=["A useful asymptotic conclusion still requires a uniform bound on D_N."],
        ),
        RHEquation(
            equation_id="rh.tail_attack_iii_target",
            latex=r"\frac{A_N^2}{N}=o(\log^2N),\qquad \frac{D_N}{N^2}=o(\log^2N)",
            description="Tail Attack III sufficient targets after the covariance contribution C_N/N is reduced to O(1).",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
            dependencies=["A_N=o(sqrt(N) log N) or equivalent", "D_N=o(N^2 log^2 N) or a sharper transfer theorem"],
            source_ids=["internal-rh-tail-attack-iii"],
            notes=["No hidden PNT-strength, RH-strength, or Möbius-randomness assumption is accepted."],
        ),
        RHEquation(
            equation_id="rh.tail_weighted_mobius_mellin",
            latex=r"W(x)=\sum_{n\le x}\mu(n)\log(x/n),\qquad \int_1^\infty W(x)x^{-s-1}\,dx=\frac{1}{s^2\zeta(s)}\quad(\Re s>1)",
            description="Exact Mellin transform exposing the zeta-zero sensitivity of the mean-component route.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iv", "dirichlet-series-1-over-zeta"],
            notes=["Near-square-root growth claims for W or A_N are proof-grade dependencies and cannot be imported as generic PNT cancellation."],
        ),
        RHEquation(
            equation_id="rh.tail_discrepancy_period_bound",
            latex=r"D_N\le 2L_NM_N,\qquad L_N=\operatorname{lcm}(1,\ldots,N)",
            description="Elementary fixed-N deterministic discrepancy bound over one residual period.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iv"],
            notes=["The bound is asymptotically weak because L_N grows rapidly."],
        ),
        RHEquation(
            equation_id="rh.tail_iv_dashboard_bound",
            latex=r"T_N\le\frac{A_N^2}{N}+\frac{C_N}{N}+\frac{D_N}{N^2}",
            description="Component-wise weighted-tail upper bound used by the Tail Attack IV proof-dependency dashboard.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-iii-calculus", "internal-rh-tail-attack-iv"],
        ),
        RHEquation(
            equation_id="rh.tail_attack_iv_target",
            latex=r"\frac{A_N^2}{N}=o(\log^2N),\quad \frac{C_N}{N}=O(1),\quad \frac{D_N}{N^2}=o(\log^2N)",
            description="Tail Attack IV dependency graph: covariance is proved; mean and discrepancy remain proof obligations.",
            proof_status=RHProofStatus.CONJECTURAL_LEMMA,
            dependencies=["mean-component growth theorem", "Tail Attack II covariance bound", "uniform discrepancy growth theorem"],
            source_ids=["internal-rh-tail-attack-iv"],
            notes=["The combined tail theorem remains blocked until every dependency is proved."],
        ),
        RHEquation(
            equation_id="rh.tail_fixed_n_certificate",
            latex=r"\int_N^C\frac{|R_N(y)|^2}{y^2}dy\le T_N\le\int_N^C\frac{|R_N(y)|^2}{y^2}dy+\frac{B_N^2}{C},\quad B_N=\log N+\sum_{n\le N}|\mu(n)|(\log N-\log n)",
            description="Certified fixed-N tail enclosure from an exact finite window and an unconditional pointwise remainder bound.",
            proof_status=RHProofStatus.SYMBOLIC_IDENTITY,
            source_ids=["internal-rh-tail-attack-i"],
            notes=["This certificate is finite-N only and cannot certify T_N=o(log^2 N)."],
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

        from .tail_attack import tail_attack_snapshot
        tail_snapshot = tail_attack_snapshot()
        calculations.append(
            ScienceCalculation(
                equation_id="rh.tail_attack_i_snapshot",
                inputs={"N": tail_snapshot["n"], "cutoff": tail_snapshot["cutoff"]},
                result=tail_snapshot,
                provenance_class=ProvenanceClass.NUMERICAL_MATHEMATICS,
                evidence_status="SUPPORTED",
                assumptions=["finite N", "finite cutoff", "exact symbolic tail identities"],
                limitations=list(tail_snapshot["limitations"]),
                source_ids=["sara-rh-tail-attack-i"],
                validation_status="NUMERICAL_EVIDENCE",
            )
        )

        from .gcd_covariance import tail_attack_ii_snapshot
        tail_ii_snapshot = tail_attack_ii_snapshot()
        calculations.append(
            ScienceCalculation(
                equation_id="rh.tail_attack_ii_snapshot",
                inputs={"N": tail_ii_snapshot["n"]},
                result=tail_ii_snapshot,
                provenance_class=ProvenanceClass.NUMERICAL_MATHEMATICS,
                evidence_status="SUPPORTED",
                assumptions=[
                    "exact Jordan-totient covariance decomposition",
                    "elementary harmonic and dyadic covariance bound",
                    "finite-N diagnostics",
                ],
                limitations=list(tail_ii_snapshot["remaining_uniform_gaps"]),
                source_ids=["sara-rh-tail-attack-ii"],
                validation_status="NUMERICAL_EVIDENCE",
            )
        )

        from .tail_attack_iii import tail_attack_iii_snapshot
        tail_iii_snapshot = tail_attack_iii_snapshot()
        calculations.append(
            ScienceCalculation(
                equation_id="rh.tail_attack_iii_snapshot",
                inputs={"N": tail_iii_snapshot["n"]},
                result=tail_iii_snapshot,
                provenance_class=ProvenanceClass.NUMERICAL_MATHEMATICS,
                evidence_status="SUPPORTED",
                assumptions=[
                    "exact centered residual decomposition",
                    "exact fixed-N period energy",
                    "exact integration-by-parts transfer identity",
                    "finite-N discrepancy computation",
                ],
                limitations=list(tail_iii_snapshot["remaining_uniform_gaps"]),
                source_ids=["sara-rh-tail-attack-iii"],
                validation_status="NUMERICAL_EVIDENCE",
            )
        )

        from .tail_attack_iv import tail_attack_iv_snapshot
        tail_iv_snapshot = tail_attack_iv_snapshot()
        calculations.append(
            ScienceCalculation(
                equation_id="rh.tail_attack_iv_snapshot",
                inputs={"N": tail_iv_snapshot["dashboard"]["n"]},
                result=tail_iv_snapshot,
                provenance_class=ProvenanceClass.NUMERICAL_MATHEMATICS,
                evidence_status="SUPPORTED",
                assumptions=[
                    "sourced external Mertens/PNT comparison ladder",
                    "Tail Attack II covariance theorem",
                    "fixed-N discrepancy and subperiod diagnostics",
                    "Tail Attack III weighted-transfer inequality",
                ],
                limitations=[
                    "Known unconditional Mertens bounds do not reach the required mean-component scale.",
                    "Finite period/subperiod balancing does not certify a uniform discrepancy asymptotic.",
                    "The combined weighted-tail asymptotic remains blocked.",
                ],
                source_ids=["sara-rh-tail-attack-iv"],
                validation_status="NUMERICAL_EVIDENCE",
            )
        )

        false_promotion = gate.evaluate(
            claim="RH proved",
            proof_status=RHProofStatus.NUMERICAL_EVIDENCE,
            finite_n_only=True,
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
                "conversation_cross_reference_complete": True,
                "tail_attack_i": {
                    "enabled": True,
                    "asymptotic_certified": False,
                    "fixed_n_certificate": True,
                    "period_mean_square_identity": True,
                },
                "tail_attack_ii": {
                    "enabled": True,
                    "gcd_covariance_jordan_decomposition": True,
                    "uniform_covariance_linear_bound_proved": True,
                    "cross_layer_cancellation": False,
                    "uniform_tail_certified": False,
                    "remaining_gap": "mean-component plus cumulative-energy discrepancy / period-to-tail transfer",
                },
                "tail_attack_iii": {
                    "enabled": True,
                    "centered_residual_decomposition": True,
                    "mertens_mean_identity": True,
                    "exact_weighted_transfer_identity": True,
                    "fixed_n_discrepancy_certificate": True,
                    "mean_uniform_target_certified": False,
                    "discrepancy_uniform_target_certified": False,
                    "uniform_tail_certified": False,
                },
                "tail_attack_iv": {
                    "enabled": True,
                    "program": "Mean + Discrepancy Growth Program",
                    "mertens_bound_catalog": True,
                    "subperiod_discrepancy_analyzer": True,
                    "combined_tail_dashboard": True,
                    "covariance_uniform_status": "proved",
                    "mean_uniform_status": "blocked",
                    "discrepancy_uniform_status": "conjectural",
                    "uniform_tail_status": "blocked",
                },
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
