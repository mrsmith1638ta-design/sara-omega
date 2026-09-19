# SARA-OMEGA Riemann Hypothesis Research Engine

## Status boundary

The Riemann Hypothesis (RH) remains an unsolved Millennium Prize Problem. This engine is a governed research system, not a proof claim. It separates exact symbolic identities, finite numerical evidence, conjectural lemmas, and any future formally certified proof artifact.

External cross-reference:
- Clay Mathematics Institute, Riemann Hypothesis: https://www.claymath.org/millennium/Riemann-Hypothesis/
- L. Báez-Duarte, *A strengthening of the Nyman-Beurling criterion for the Riemann Hypothesis*, arXiv:math/0202141.
- S. Bettin, J. B. Conrey, D. W. Farmer, *An optimal choice of Dirichlet polynomials for the Nyman-Beurling criterion*, arXiv:1211.5191.
- Vasyunin/cotangent-sum Gram literature is used only for finite Gram evaluation and is not treated as an RH proof.
- NIST DLMF, Chapter 24, periodic Bernoulli functions: https://dlmf.nist.gov/24.2.iii
- Encyclopedia of Mathematics, Wirsing theorems / PNT form M(x)=o(x): https://encyclopediaofmath.org/wiki/Wirsing_theorems
- E. S. Lee and N. Leong, *New explicit bounds for Mertens function and the reciprocal of the Riemann zeta-function*, arXiv:2208.06141.

## Proof-status states

Every RH object is tagged with exactly one of:

- `SYMBOLIC_IDENTITY`
- `NUMERICAL_EVIDENCE`
- `CONJECTURAL_LEMMA`
- `FORMAL_PROOF_CERTIFIED`

`FORMAL_PROOF_CERTIFIED` is fail-closed: a certificate reference and a proved infinite-limit implication are required. The engine never self-assigns that state.

## Tail Attack I

Tail Attack I focuses SARA on the post-`N` bottleneck:

```text
J_N = integral_1^N |theta_N y - psi(y)|^2 dy/y^2
    + integral_N^infinity |theta_N y - psi_N(y)|^2 dy/y^2.
```

The engine computes a finite tail-window diagnostic:

```text
integral_N^X |theta_N y - psi_N(y)|^2 dy/y^2
```

and samples the exact sawtooth identity:

```text
theta_N*y - psi_N(y)
  = log N + sum_{n<=N} mu(n)(log N - log n){y/n}.
```

This lets SARA compare cancellation ideas, fractional-part averaging claims, and proposed upper bounds without calling them proof. The post-cutoff tail remains explicitly uncomputed, and the adversarial gate rejects tail-bound claims that rely on hidden RH assumptions, zeta-zero assumptions, Lindelof-strength input, or unproved square-root cancellation.

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

The exact Möbius divisor identities stored alongside that reduction are

[
\sum_{n\le y}\mu(n)\left\lfloor\frac yn\right\rfloor=1
]

and

[
\sum_{n\le y}\mu(n)\log n\left\lfloor\frac yn\right\rfloor=-\psi(y).
]

Therefore the bottleneck splits exactly as

[
\boxed{
J_N
=
\int_1^N|\theta_Ny-\psi(y)|^2\frac{dy}{y^2}
+
\int_N^\infty|\theta_Ny-\psi_N(y)|^2\frac{dy}{y^2}
}.
]

The post-(N) residual also has the exact fractional-part representation

[
\boxed{
\theta_Ny-\psi_N(y)
=
\log N
+
\sum_{n\le N}\mu(n)(\log N-\log n)
\left\{\frac yn\right\}.
}
]

This identity is useful for tail analysis, but it is **not** by itself a sufficient asymptotic bound.

The current sufficient target is

[
\boxed{
\theta_N=O(1)
\quad\text{and}\quad
J_N=o(\log^2N)
}.
]

The corresponding conditional implication chain is recorded explicitly:

[
\boxed{
\theta_N=O(1),\ J_N=o(\log^2N)
\Longrightarrow
\|e_N\|_2^2\to0
\Longrightarrow
d_N\to0
\Longrightarrow
RH.
}
]

If both asymptotic statements are proved unconditionally, then the displayed norm identity forces (\|e_N\|_2\to0); the Báez-Duarte criterion would then imply RH. **The engine does not currently contain such a proof.** The two asymptotic statements and the implication chain are therefore fail-closed as `CONJECTURAL_LEMMA` objects until their hypotheses are certified.

The earlier stronger target

[
\int_1^N|\psi(y)-\theta_Ny|^2\frac{dy}{y^2}=O(\log N)
]

is retained as a potentially useful stronger estimate, but it is not required by the present reduction.

## Tail Attack I

Tail Attack I focuses only on the post-(N) term

[
T_N=
\int_N^\infty
|R_N(y)|^2\frac{dy}{y^2},
\qquad
R_N(y)=\theta_Ny-\psi_N(y).
]

From the exact sawtooth representation,

[
R_N(y)
=
\log N+
\sum_{n\le N}a_{n,N}\left\{\frac yn\right\},
\qquad
a_{n,N}=\mu(n)(\log N-\log n),
]

SARA records the exact fixed-(N) periodicity

[
\boxed{
R_N(y+L_N)=R_N(y),
\qquad
L_N=\operatorname{lcm}(1,\ldots,N).
}
]

Writing each sawtooth as its centered periodic Bernoulli component plus (1/2),
the full-period mean square is

[
\boxed{
M_N
=
\left(
\log N+\frac12\sum_{n\le N}a_{n,N}
\right)^2
+
\frac1{12}
\sum_{m,n\le N}
a_{m,N}a_{n,N}
\frac{\gcd(m,n)^2}{mn}.
}
]

This is an exact structural identity for fixed (N). It is **not** by itself a
bound on the weighted tail beginning at (y=N), because (L_N) grows rapidly.

Tail Attack I also defines

[
B_N
=
\log N+
\sum_{n\le N}|a_{n,N}|,
]

so the fractional-part representation gives the unconditional pointwise bound

[
|R_N(y)|\le B_N.
]

For any integer cutoff (C>N), the existing unit-interval integrator computes

[
W_{N,C}
=
\int_N^C |R_N(y)|^2\frac{dy}{y^2}
]

exactly up to floating-point evaluation of the closed forms, and the remaining
tail obeys

[
0\le
\int_C^\infty|R_N(y)|^2\frac{dy}{y^2}
\le
\frac{B_N^2}{C}.
]

Therefore SARA emits the finite-(N) certificate

[
\boxed{
W_{N,C}
\le T_N
\le
W_{N,C}+\frac{B_N^2}{C}.
}
]

This is useful for reproducible fixed-(N) research and for falsifying proposed
tail estimates. It does **not** establish (T_N=o(\log^2N)). The proof gate
explicitly blocks promotion from finite tail certificates to a uniform
(N\to\infty) asymptotic statement.

Current Tail Attack I outputs include:

- exact residual period;
- exact full-period mean-square formula;
- direct small-(N) period validation;
- unconditional pointwise residual bound;
- exact finite tail window;
- certified remainder upper bound;
- normalized finite-(N) upper bound versus (\log^2N);
- an explicit `asymptotic_certified=false` field.

The next research question is whether the Möbius-weighted gcd quadratic form,
or another cancellation mechanism, can yield a uniform estimate strong enough
to improve the crude (B_N^2/C) remainder in a way that survives
(N\to\infty).

## Tail Attack II: gcd covariance analyzer

Tail Attack II rewrites the fixed-(N) covariance

[
C_N=
\frac1{12}
\sum_{m,n\le N}
a_{m,N}a_{n,N}
\frac{\gcd(m,n)^2}{mn}
]

using the Jordan totient identity

[
\gcd(m,n)^2=
\sum_{d\mid m,\ d\mid n}J_2(d).
]

Therefore

[
\boxed{
C_N=
\frac1{12}
\sum_{d\le N}
J_2(d)
\left(
\sum_{d\mid m\le N}\frac{a_{m,N}}m
\right)^2.
}
]

This is a positive sum of squares. It shows that there is **no cancellation
between divisor layers**. Any arithmetic cancellation in the original gcd
double sum occurs inside the layer sums themselves.

Because (a_{m,N}=\mu(m)(\log N-\log m)), nonsquarefree divisor layers vanish.
For squarefree (d), write

[
H_d(N/d)=
\sum_{\substack{k\le N/d\\(k,d)=1}}
\frac{\mu(k)\log((N/d)/k)}{k}.
]

Then

[
\boxed{
C_N=
\frac1{12}
\sum_{\substack{d\le N\\\mu(d)^2=1}}
\frac{J_2(d)}{d^2}
H_d(N/d)^2.
}
]

The engine verifies the direct gcd sum, the Jordan decomposition, and the
squarefree/coprime decomposition against each other at finite (N).

An elementary bound requires no RH assumption and no Möbius-randomness
assumption. Let (L_d=\log(N/d)). Then

[
|H_d(N/d)|
\le
\sum_{k\le N/d}\frac{L_d-\log k}{k}
\le
L_d(1+L_d).
]

Since (J_2(d)/d^2\le1), dyadic grouping gives the explicit uniform estimate

[
\boxed{
C_N\le K N,
\qquad
K=
\frac{
12(\log2)^2+
104(\log2)^3+
300(\log2)^4
}{12}
<9.14.
}
]

So the gcd covariance component itself is now unconditionally controlled by a
linear bound. This is a real reduction, but **it does not prove the weighted
tail bound**. The full period mean square also contains the mean component

[
\left(
\log N+\frac12\sum_{n\le N}a_{n,N}
\right)^2,
]

and a period average does not automatically control the weighted tail starting
at (y=N).

Tail Attack II therefore records the conditional transfer lemma. If

[
A_N(x)=\int_N^x R_N(y)^2dy
\le
M_N(x-N)+D_N
\qquad\text{for every }x\ge N,
]

then integration by parts gives

[
\boxed{
T_N
\le
\frac{M_N}{N}
+
\frac{D_N}{N^2}.
}
]

The implication is elementary; the required uniform bound on (D_N) is not
currently proved. The remaining Tail Attack II research gaps are therefore:

- control the period mean component strongly enough;
- obtain a uniform cumulative-energy discrepancy estimate, or another valid
  period-to-tail transfer;
- combine those estimates with the proved covariance (O(N)) bound without
  importing RH, zeta-zero location, square-root cancellation, or Möbius
  randomness as an assumption.

The red-team gate explicitly rejects the inference

    C_N = O(N)  therefore  T_N = o(log^2 N)

unless the missing mean-component and period-to-tail estimates are supplied.

## Tail Attack III: mean component + weighted-tail transfer

Tail Attack III starts from the exact centered decomposition

[
\boxed{
R_N(y)=A_N+S_N(y)
}
]

with

[
A_N=
\log N+
\frac12
\sum_{n\le N}\mu(n)(\log N-\log n)
]

and

[
S_N(y)=
\sum_{n\le N}
a_{n,N}
\left(
\left\{\frac yn\right\}-\frac12
\right).
]

The mean component also has the exact partial-summation form

[
\boxed{
A_N=
\log N+
\frac12
\int_1^N
\frac{M(t)}{t}\,dt,
\qquad
M(t)=\sum_{n\le t}\mu(n).
}
]

This identity exposes the precise Möbius summatory quantity that must be
controlled. The engine does not insert any unproved cancellation estimate for
(M(t)).

The full-period energy is now tracked component-by-component:

[
\boxed{
M_N=A_N^2+C_N.
}
]

Tail Attack II already supplies the unconditional covariance bound

[
C_N=O(N).
]

Therefore the covariance contribution to (M_N/N) is only (O(1)), which is
(o(\log^2 N)). The remaining mean-component target is

[
\boxed{
\frac{A_N^2}{N}=o(\log^2N),
}
]

equivalently

[
A_N=o(\sqrt N\log N).
]

Tail Attack III next defines the cumulative-energy discrepancy

[
E_N(x)=
\int_N^xR_N(y)^2\,dy
-
M_N(x-N).
]

For fixed (N), both (R_N^2) and (E_N) are periodic with period
(L_N=\operatorname{lcm}(1,\ldots,N)). Define

[
D_N=\sup_{x\ge N}|E_N(x)|.
]

Integration by parts gives the exact weighted-tail transfer identity

[
\boxed{
T_N=
\frac{M_N}{N}
+
2\int_N^\infty
\frac{E_N(y)}{y^3}\,dy.
}
]

Hence

[
\boxed{
\left|
T_N-\frac{M_N}{N}
\right|
\le
\frac{D_N}{N^2}.
}
]

For modest fixed (N), SARA computes (D_N) over one full period. On each unit
interval, extrema of (E_N) can occur only at endpoints or where

[
R_N(y)^2=M_N.
]

This yields a reproducible fixed-(N) periodic-transfer certificate without
identifying the period average with the weighted tail.

After the Tail Attack II covariance reduction, the remaining Tail Attack III
uniform targets are

[
\boxed{
\frac{A_N^2}{N}=o(\log^2N),
\qquad
\frac{D_N}{N^2}=o(\log^2N).
}
]

If both hold, then the post-(N) weighted tail satisfies the required little-o
bound. These estimates are **not currently certified**.

The red-team gate rejects all of the following shortcuts:

- treating a finite-period average as the weighted tail;
- omitting the explicit discrepancy term (D_N);
- assuming Möbius randomness or square-root cancellation;
- inserting an unproved PNT-strength cancellation estimate;
- using RH or an RH-equivalent zero-location statement;
- promoting finite values of (A_N), (D_N), or (T_N) to an asymptotic theorem.

## Tail Attack IV: Mean + Discrepancy Growth Program

Tail Attack IV converts the remaining weighted-tail problem into a live proof-dependency graph:

[
\boxed{
T_N
\le
\frac{A_N^2}{N}
+
\frac{C_N}{N}
+
\frac{D_N}{N^2}.
}
]

Each term carries separate finite-(N) and uniform-asymptotic status.

### Mean-component attack

The exact identity is

[
A_N=
\log N+
\frac12\int_1^N\frac{M(t)}{t}\,dt.
]

SARA stores a sourced comparison ladder rather than silently importing cancellation:

- elementary: (|M(x)|\le x), giving only an O(N)-scale mean bound;
- Prime Number Theorem: (M(x)=o(x)), established but still insufficient for the Tail Attack IV target;
- Korobov--Vinogradov/Walfisz zero-free-region scale:
  [
  M(x)\ll x\exp\!\left(-c(\log x)^{3/5}(\log\log x)^{-1/5}\right),
  ]
  also unconditional, but still not strong enough to establish (A_N=o(\sqrt N\log N)).

If

[
W(x)=\sum_{n\le x}\mu(n)\log(x/n),
]

then for (\Re s>1),

[
\boxed{
\int_1^\infty W(x)x^{-s-1}\,dx
=
\frac{1}{s^2\zeta(s)}.
}
]

This makes the mean route explicitly zeta-zero sensitive. Near-square-root bounds are treated as proof-grade dependencies, not routine PNT input.

The current mean target remains

[
\boxed{
\frac{A_N^2}{N}=o(\log^2N).
}
]

Its uniform dashboard status is BLOCKED until a valid proof is attached.

### Discrepancy attack

Tail Attack IV keeps

[
E_N(x)=
\int_N^xR_N(y)^2\,dy-M_N(x-N)
]

and

[
D_N=\sup_{x\ge N}|E_N(x)|.
]

For manageable fixed N, SARA profiles deterministic accumulation over subperiod blocks. These are FINITE_CERTIFIED evidence only.

There is also an unconditional fixed-N fallback:

[
\boxed{
D_N\le2L_NM_N,
\qquad
L_N=\operatorname{lcm}(1,\ldots,N).
}
]

This bound is valid but asymptotically weak because L_N grows rapidly. The engine marks it PROVED but asymptotically_sufficient=false.

The required discrepancy target remains

[
\boxed{
\frac{D_N}{N^2}=o(\log^2N).
}
]

Its uniform status is CONJECTURAL.

### Combined live dashboard

For tractable finite N, SARA emits component statuses:

- mean A_N^2/N: finite_status=FINITE_CERTIFIED, uniform_status=BLOCKED;
- covariance C_N/N: finite_status=FINITE_CERTIFIED, uniform_status=PROVED;
- discrepancy D_N/N^2: finite_status=FINITE_CERTIFIED, uniform_status=CONJECTURAL;
- combined weighted tail: finite_status=FINITE_CERTIFIED, uniform_status=BLOCKED.

The Tail Attack IV red-team gate blocks unsourced Mertens/PNT/zero-free-region bounds, hidden RH or zeta-zero-location assumptions, Möbius-randomness or square-root-cancellation assumptions, finite subperiod patterns promoted to a uniform D_N rate, and any combined tail theorem while a required dependency remains blocked or conjectural.

## Tail Attack V: Mean Obstruction Audit + Discrepancy Growth Search

Tail Attack V does not claim that RH is closer by assertion. It hardens the live proof boundary exposed by Tail Attack IV.

The mean side is audited as

[
\boxed{
A_N=o(\sqrt N\log N)
}
]

or equivalently

[
\boxed{
\frac{A_N^2}{N}=o(\log^2N).
}
]

SARA marks this dependency as BLOCKED and RH-sensitive because the exact weighted Mobius transform is

[
\int_1^\infty
\left(\sum_{n\le x}\mu(n)\log\frac{x}{n}\right)x^{-s-1}\,dx
=
\frac{1}{s^2\zeta(s)}
\qquad(\Re s>1).
]

That denominator means near-square-root mean control is not treated as ordinary random-looking Mobius cancellation. It is a proof-grade dependency until someone proves it without assuming RH or an RH-equivalent zero-location statement.

The discrepancy side remains

[
\boxed{
\frac{D_N}{N^2}=o(\log^2N).
}
]

Tail Attack V keeps finite subperiod and fixed-period diagnostics, but their uniform status remains CONJECTURAL. Finite balancing patterns are allowed as search evidence only.

The Tail Attack V dependency graph is therefore:

- mean obstruction: BLOCKED;
- covariance: PROVED by Tail Attack II;
- discrepancy growth: CONJECTURAL;
- combined weighted-tail theorem: BLOCKED.

Tail Attack V's red-team gate blocks zeta-zero shortcuts, near-square-root Mobius assumptions, finite discrepancy promotion, and any combined tail theorem until the mean obstruction and discrepancy-growth theorem are both actually proved.

## RH Route Pivot

The Tail Attack I-V naming sequence stops here.

The reason is mathematical, not cosmetic:

- covariance was genuinely reduced;
- the mean term appears RH-strength;
- the discrepancy term remains genuinely open;
- continuing to manufacture new Tail Attack phases would risk renaming the same barrier.

SARA now splits the research into a new RH Route Pivot.

### Pivot A: Signed Cancellation Recovery

Pivot A keeps the exact signed transfer identity

[
T_N=
\frac{M_N}{N}
+2\int_N^\infty E_N(y)y^{-3}\,dy
]

instead of immediately replacing the second term by the absolute bound

[
\frac{D_N}{N^2}.
]

The research target is to recover cancellation in the signed integral or cross terms that the absolute-value estimate destroys. Its status is RESEARCH_TARGET, not proved.

### Pivot B: Mean-Zero Constrained Coefficients

Pivot B changes the finite optimization problem. Instead of forcing the Selberg mean term to be small through an RH-sensitive Möbius estimate, SARA solves the constrained Gram problem

[
\min_c
\left(1-2v_N^Tc+c^TG_Nc\right)
]

subject to

[
\sum_{n\le N}c_n=2
]

and optionally also

[
\sum_{n\le N}\frac{c_n}{n}=0.
]

The finite solver uses the KKT system

[
\begin{pmatrix}
G_N&A\\
A^T&0
\end{pmatrix}
\begin{pmatrix}
c\\ \lambda
\end{pmatrix}
=
\begin{pmatrix}
v_N\\ b
\end{pmatrix}.
]

SARA records the exact finite penalty

[
\Delta_N^{\rm constrained}
=
Q_N(c_N^{\rm constrained})-d_N^2.
]

The new central question is

[
\boxed{
\Delta_N^{\rm constrained}\to0?
}
]

If this penalty tends to zero, the route has genuinely changed: the mean obstruction is removed algebraically rather than proved small by an RH-strength estimate. At present this is CONJECTURAL and finite-N evidence cannot certify the limit.

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
7. covariance O(N) alone -> weighted-tail little-o theorem
8. period mean-square control -> tail theorem without a proved transfer/discrepancy estimate
9. finite-period average -> weighted tail without explicit D_N control
10. unproved PNT-strength or Möbius-randomness input -> mean-component theorem
11. unsourced Mertens/PNT/zero-free-region estimate -> mean-component theorem
12. finite subperiod balancing -> uniform discrepancy theorem
13. combined Tail IV dashboard -> asymptotic tail theorem while any dependency is blocked/conjectural
14. zero-structure or near-square-root mean shortcut -> Tail V mean theorem without proof-grade certification
15. Tail V mean audit + finite discrepancy diagnostics -> combined weighted-tail theorem
16. finite constrained-Gram penalty data -> RH Route Pivot theorem
17. signed-transfer numerical cancellation -> uniform Pivot A theorem

The runtime truth gate and `tools/riemann_adversarial_gate.py` enforce these boundaries.


## Conversation cross-reference registry

The runtime equation registry now includes the full set of RH objects used in the current research thread, including:

- `rh.rho_n`
- `rh.constructive_residual`
- `rh.selberg_coefficients`
- `rh.theta`
- `rh.psi_n`
- `rh.pointwise_residual`
- `rh.mobius_divisor_identity`
- `rh.log_mobius_divisor_identity`
- `rh.finite_psi`
- `rh.finite_range_residual`
- `rh.l2_exact`
- `rh.j_n`
- `rh.j_split`
- `rh.tail_sawtooth`
- `rh.tail_periodicity`
- `rh.tail_period_mean_square`
- `rh.tail_covariance_jordan`
- `rh.tail_covariance_squarefree_layers`
- `rh.tail_covariance_linear_bound`
- `rh.tail_energy_transfer`
- `rh.tail_attack_ii_target`
- `rh.tail_centered_decomposition`
- `rh.tail_mean_mertens`
- `rh.tail_period_energy_components`
- `rh.tail_discrepancy`
- `rh.tail_transfer_exact`
- `rh.tail_transfer_error`
- `rh.tail_attack_iii_target`
- `rh.tail_weighted_mobius_mellin`
- `rh.tail_discrepancy_period_bound`
- `rh.tail_iv_dashboard_bound`
- `rh.tail_attack_iv_target`
- `rh.tail_v_mean_obstruction_audit`
- `rh.tail_v_discrepancy_growth_search`
- `rh.tail_attack_v_target`
- `rh.route_pivot_signed_transfer`
- `rh.route_pivot_mean_zero_constraints`
- `rh.route_pivot_penalty_target`
- `rh.stronger_finite_target`
- `rh.sufficient_target`
- `rh.sufficient_implication_chain`
- `rh.baez_duarte_limit`

This is the intended integration point for future RH derivations. New calculations must enter through the equation registry and inherit a proof-status label before they are eligible for synthesis.
