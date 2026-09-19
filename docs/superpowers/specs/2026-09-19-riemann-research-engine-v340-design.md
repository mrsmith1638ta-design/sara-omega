# SARA OMEGA ChatGPT V3.4.0 Riemann Research Engine Design

**Date:** 2026-09-19
**Status:** Design for SARA OMEGA ChatGPT V3.4.0 integration
**Target repository:** `sara-omega-tutor-pr-clean`
**Target version:** `SARA OMEGA ChatGPT V3.4.0`

## 1. Purpose

Fuse a governed Riemann Hypothesis research engine into SARA OMEGA ChatGPT V3.4.0.

The engine gives SARA a structured way to encode, compute, test, and adversarially review the Nyman-Beurling/Baez-Duarte approximation framework without allowing numerical evidence, quantum analogies, spectral patterns, or unverified lemmas to be promoted into a proof.

The engine does not claim to prove RH by default. It makes the proof target explicit:

```text
theta_N = O(1)
J_N = o(log^2 N)
```

where

```text
J_N = integral_1^infinity |theta_N y - psi_N(y)|^2 dy / y^2.
```

If SARA ever verifies those bounds unconditionally and without circular assumptions, the Baez-Duarte/Nyman-Beurling framework would let SARA mark the result as a candidate proof route. A final "RH proved" status still requires formal proof certification.

## 2. Governing Rule

SARA OMEGA remains the final synthesis and governance layer.

The Riemann engine is a research specialist. It cannot:

- declare RH proved from finite computation;
- infer an infinite limit from observed monotone numerical behavior;
- assume RH, zero-free regions equivalent to RH, Lindelof-strength estimates, or hidden zeta-zero hypotheses inside a proof route;
- treat quantum/spectral interpretation as theorem certification;
- bypass the OMEGA Council, High-Level Truth Gate, or signed verdict ledger.

All outputs must carry one of four proof statuses:

- `NUMERICAL_EVIDENCE`
- `SYMBOLIC_IDENTITY`
- `CANDIDATE_LEMMA`
- `FORMAL_PROOF_CERTIFIED`

Only `FORMAL_PROOF_CERTIFIED` may support user-facing proof language.

## 3. Mathematical Framework

The engine represents the reciprocal approximation problem:

```text
d_N = inf_c || chi_(0,1) - sum_{k<=N} c_k {1/(kx)} ||_2.
```

It tracks the optimizer:

```text
c_N = G_N^{-1} v_N
```

and the raw Mobius vector:

```text
m_N = (-mu(1), -mu(2), ..., -mu(N))^T.
```

The hidden correction is:

```text
delta_N = c_N - m_N
r_N = v_N - G_N m_N
G_N delta_N = r_N.
```

The engine also records the exact Gram-norm identity:

```text
Q_N(m_N) - d_N^2 = delta_N^T G_N delta_N = r_N^T G_N^{-1} r_N.
```

It supports the augmented determinant identity:

```text
d_N^2 = det(mathcal_G_N) / det(G_N)
```

where

```text
mathcal_G_N = [[1, v_N^T], [v_N, G_N]].
```

It supports recursive Schur complement updates:

```text
s_N = a_N - g_N^T G_N^{-1} g_N
t_N = b_N - g_N^T G_N^{-1} v_N
d_{N+1}^2 = d_N^2 - t_N^2 / s_N.
```

## 4. Selberg-Type Coefficient Target

The engine includes the Selberg-style coefficient family:

```text
c_n(N) = -mu(n) * (1 - log(n) / log(N))
```

with the transformed error identity:

```text
||e_N||_2^2 =
theta_N^2 / log^2(N)
+ (1 / log^2(N)) * integral_1^infinity |theta_N y - psi_N(y)|^2 dy / y^2.
```

It names the bottleneck:

```text
J_N = integral_1^infinity |theta_N y - psi_N(y)|^2 dy / y^2.
```

The engine treats the sufficient target as:

```text
theta_N = O(1)
J_N = o(log^2 N).
```

This target is stored as a candidate proof route, not as an established theorem.

## 5. Tail Split

The engine splits:

```text
J_N = integral_1^N (...) + integral_N^infinity (...).
```

For `1 <= y <= N`, it records the simplification:

```text
psi_N(y) = psi(y)
```

using the classical divisor identities:

```text
sum_{n<=y} mu(n) floor(y/n) = 1
sum_{n<=y} mu(n) log(n) floor(y/n) = -psi(y).
```

For `y > N`, the engine keeps a separate tail object. The tail may be studied numerically or symbolically, but no tail estimate may be marked as proved unless every inequality and summation transition is justified without RH-equivalent assumptions.

## 6. Smooth and Mellin Spectral Research

The engine stores exploratory bases as research evidence:

- smooth correction modes;
- normalized Gram eigenmodes;
- blind Mellin-frequency modes `cos(t log k)` and `sin(t log k)`;
- optional Dirichlet-character extensions.

These tools may produce candidate lemmas or numerical evidence. They may not certify RH.

For a smooth basis `B`, the engine represents:

```text
S = B^T G B
y = B^T r
beta = S^{-1} y
r_perp = r - G B beta
```

For a Mellin frequency pair `X_t`, it represents:

```text
C_t = X_t^T G X_t - X_t^T G B S^{-1} B^T G X_t
z_t = X_t^T r_perp
Delta_N(t) = z_t^T C_t^{-1} z_t
R_N(t) = Delta_N(t) / (Q_smooth - d_N^2).
```

The scan must be blind with respect to known zeta-zero ordinates. Comparison to known spectral quantities is permitted only after the scan results are recorded.

## 7. Quantum and Dilation Interpretation

The engine may describe the dilation Hamiltonian:

```text
H_D = -i(x d/dx + 1/2)
```

and the Mellin mode:

```text
k^{-1/2-it}.
```

This layer is interpretive and heuristic unless connected to formal spectral lemmas. It cannot promote a result beyond its proof status.

## 8. Runtime Components

The V3.4.0 engine should be implemented under:

```text
app/science/riemann/
```

Recommended modules:

- `models.py` - proof status, result payloads, coefficient families, and route records.
- `mobius.py` - Mobius, Chebyshev, and finite arithmetic helpers.
- `baez_duarte.py` - Nyman-Beurling/Baez-Duarte identities and sufficient target encoding.
- `vasyunin.py` - Gram matrix, optimizer, determinant, residual, and Schur complement computations.
- `selberg.py` - Selberg coefficient route and `J_N` decomposition.
- `spectral.py` - smooth and Mellin residual scans.
- `proof_gate.py` - deterministic classification and forbidden-assumption checks.
- `provider.py` - SARA science specialist wrapper.

The router should recognize Riemann, RH, Nyman-Beurling, Baez-Duarte, Vasyunin, Mobius, Chebyshev psi, zeta, Mellin, and dilation-Hamiltonian requests.

## 9. Truth Gate Extension

The High-Level Truth Gate must reject or qualify:

- "RH is proved" without `FORMAL_PROOF_CERTIFIED`;
- "finite tests prove the limit";
- "the optimizer converges, therefore RH";
- "quantum spectrum proves RH";
- "assume RH" inside a proof route;
- "known zero data proves all zeros";
- "numerical bound for N <= M proves asymptotic bound."

Truth-gated outputs should preserve the strongest justified wording:

- numerical evidence may support "observed for tested N";
- symbolic identities may support "algebraically verified identity";
- candidate lemmas may support "would imply RH if proved";
- formal certificates may support proof language only for the certified statement.

## 10. Adversarial Gate

The repository must include an aggressive adversarial suite that attacks:

- circular RH assumptions;
- equivalent reformulations presented as independent proof;
- hidden use of prime number theorem error terms stronger than currently known unconditionally;
- hidden use of zero-free bounds strong enough to imply RH;
- finite-to-infinite extrapolation;
- determinant-ratio numerical convergence promoted to theorem;
- Mellin-frequency coincidence with zeta zeros promoted to proof;
- quantum interpretation promoted to theorem;
- provider consensus promoted to proof;
- ChatGPT final synthesis overstating proof status.

The GitHub workflow must run the Riemann adversarial tests as part of the SARA V3.4.0 validation gate.

## 11. Source and Citation Strategy

Static mathematical framework records should live in:

```text
data/science/equations/riemann.json
data/science/sources/riemann.json
```

Source records should include Baez-Duarte/Nyman-Beurling references, Vasyunin matrix references, and any local manuscript notes. The engine may cite local notes as research notes, but external theorem claims require bibliographic source records.

## 12. Success Criteria

V3.4.0 integration is successful when SARA can:

1. encode the RH-equivalent finite approximation framework;
2. compute finite Vasyunin/Gram quantities for bounded `N`;
3. compute Selberg-style candidate coefficients and the `J_N` split;
4. store smooth and Mellin scan outputs as numerical evidence;
5. classify every result by proof status;
6. prevent unverified proof claims from surviving the Truth Gate;
7. expose the engine through the existing governed SARA `solve` path;
8. run adversarial Riemann tests in local and GitHub validation;
9. preserve all existing SARA OMEGA governance, authority, ledger, science, and deployment gates.

## 13. Non-Goals

This V3.4.0 integration does not promise to prove RH.

It also does not:

- require real quantum hardware;
- require large-scale numerical computation to pass basic CI;
- alter SARA's execution authority model;
- replace formal proof with model output;
- weaken existing science truth-gate behavior.

The engine's job is to make the attack precise, auditable, adversarially tested, and ready for formalization.
