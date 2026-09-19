# SARA-OMEGA Riemann Hypothesis Research Engine

## Status boundary

The Riemann Hypothesis (RH) remains an unsolved Millennium Prize Problem. This engine is a governed research system, not a proof claim. It separates exact symbolic identities, finite numerical evidence, conjectural lemmas, and any future formally certified proof artifact.

External cross-reference:
- Clay Mathematics Institute, Riemann Hypothesis: https://www.claymath.org/millennium/Riemann-Hypothesis/
- L. Báez-Duarte, *A strengthening of the Nyman-Beurling criterion for the Riemann Hypothesis*, arXiv:math/0202141.
- S. Bettin, J. B. Conrey, D. W. Farmer, *An optimal choice of Dirichlet polynomials for the Nyman-Beurling criterion*, arXiv:1211.5191.
- Vasyunin/cotangent-sum Gram literature is used only for finite Gram evaluation and is not treated as an RH proof.

## Proof-status states

Every RH object is tagged with exactly one of:

- `SYMBOLIC_IDENTITY`
- `NUMERICAL_EVIDENCE`
- `CONJECTURAL_LEMMA`
- `FORMAL_PROOF_CERTIFIED`

`FORMAL_PROOF_CERTIFIED` is fail-closed: a certificate reference and a proved infinite-limit implication are required. The engine never self-assigns that state.

## Nyman-Beurling / Báez-Duarte basis

[
\rho_n(x)=\left\{\frac{1}{nx}\right\},\qquad
G_{j,k}=\langle\rho_j,\rho_k\rangle
=\int_0^\infty\rho_j(x)\rho_k(x)\,dx.
]

The target vector is

[
v_k=\langle\chi_{(0,1)},\rho_k\rangle
=\frac{\log k+1-\gamma}{k}.
]

For the finite least-squares problem,

[
c_N=G_N^{-1}v_N,
\qquad
d_N^2=1-v_N^T G_N^{-1}v_N.
]

The Báez-Duarte integer-dilation criterion is represented as

[
RH\iff d_N\to0.
]

This equivalence is an established criterion; observing small finite values of (d_N) is not a proof of the limit.

## Exact quadratic residual decomposition

For any coefficient vector (a),

[
Q_N(a)=d_N^2+(a-c_N)^T G_N(a-c_N).
]

For the negative Möbius baseline,

[
r_N=v_N-G_N(-\mu),
\qquad
\delta_N=G_N^{-1}r_N.
]

These equations let SARA distinguish the best finite approximation from a chosen Möbius/Selberg candidate.

## Augmented Gram determinant and Schur recursion

Define

[
\mathcal G_N=
\begin{pmatrix}
1&v_N^T\\
v_N&G_N
\end{pmatrix},
\qquad
d_N^2=\frac{\det\mathcal G_N}{\det G_N}.
]

For the one-step extension,

[
G_{N+1}=
\begin{pmatrix}
G_N&g_N\\
g_N^T&a_N
\end{pmatrix}.
]

Set

[
s_N=a_N-g_N^TG_N^{-1}g_N>0,
\qquad
t_N=b_N-g_N^TG_N^{-1}v_N.
]

Then the exact Schur decrement is

[
d_{N+1}^2=d_N^2-\frac{t_N^2}{s_N}.
]

CI checks the recursive value against direct recomputation for finite (N).

## Corrected Mellin sign

For

[
e_N=\chi_{(0,1)}-\sum_{k\le N}c_k\rho_k,
\qquad
A_N(s)=\sum_{k\le N}c_k k^{-s},
]

the stored sign convention is

[
\mathcal M[e_N](s)=\frac{1+\zeta(s)A_N(s)}{s}.
]

The corresponding Mellin-space residual objective is built from (|1+\zeta A_N|^2), subject to the transform's valid strip and weighting.

## Current Selberg/Möbius constructive route

The current coefficients are

[
c_n=-\mu(n)\left(1-\frac{\log n}{\log N}\right).
]

Define

[
F_N(x)=\sum_{n\le N}c_n\rho_n(x),
\qquad
e_N(x)=\chi_{(0,1)}(x)-F_N(x).
]

The normalization is

[
\theta_N
=-\log N\sum_{n\le N}\frac{c_n}{n}
=\log N\sum_{n\le N}\frac{\mu(n)}n
-\sum_{n\le N}\frac{\mu(n)\log n}{n}.
]

Define the finite Möbius-floor transform

[
\psi_N(y)
=
-\log N
+\log N\sum_{n\le N}\mu(n)\left\lfloor\frac yn\right\rfloor
-\sum_{n\le N}\mu(n)\log n\left\lfloor\frac yn\right\rfloor.
]

For every (y\ge1), the exact pointwise identity is

[
e_N(1/y)
=
\frac{\theta_Ny-\psi_N(y)}{\log N}.
]

For (1\le y\le N), the classical divisor identities give

[
\psi_N(y)=\psi(y),
]

so

[
e_N(1/y)
=
\frac{\theta_Ny-\psi(y)}{\log N}.
]

## Exact L2 identity and the current bottleneck

The exact norm identity stored in SARA is

[
\boxed{
\|e_N\|_2^2
=
\frac{\theta_N^2}{\log^2N}
+
\frac1{\log^2N}
\int_1^\infty
|\theta_Ny-\psi_N(y)|^2\frac{dy}{y^2}
}.
]

Define

[
\boxed{
J_N=
\int_1^\infty
|\theta_Ny-\psi_N(y)|^2\frac{dy}{y^2}
}.
]

The current sufficient target is

[
\boxed{
\theta_N=O(1)
\quad\text{and}\quad
J_N=o(\log^2N)
}.
]

If both asymptotic statements are proved unconditionally, then the displayed norm identity forces (|e_N|_2\to0); the Báez-Duarte criterion would then imply RH. **The engine does not currently contain such a proof.** The pair of asymptotic statements is therefore tagged `CONJECTURAL_LEMMA`.

The earlier stronger target

[
\int_1^N|\psi(y)-\theta_Ny|^2\frac{dy}{y^2}=O(\log N)
]

is retained as a potentially useful stronger estimate, but it is not required by the present reduction.

## Numerical runner boundary

The finite runner may compute:

- Vasyunin Gram matrices;
- (v_N), (c_N), and (d_N^2);
- determinant ratios;
- Möbius residuals and corrections;
- Schur pairs ((s_N,t_N));
- finite Selberg residual identities;
- truncated (J_N) integrals;
- finite smooth/Mellin diagnostics.

A truncated (J_N) computation explicitly records that the tail is uncomputed. No finite (N), finite zero scan, spectral pattern, quantum analogy, or numerical convergence is accepted as proof of an infinite theorem.

## Adversarial promotion rules

CI must fail if code permits any of these transitions without formal certification:

1. `NUMERICAL_EVIDENCE -> RH proved`
2. `CONJECTURAL_LEMMA -> theorem`
3. finite (N) -> (N\to\infty)
4. a derivation that assumes RH -> proof of RH
5. spectral/quantum evidence -> theorem certification
6. symbolic identity alone -> proof of the missing asymptotic limit

The runtime truth gate and `tools/riemann_adversarial_gate.py` enforce these boundaries.
