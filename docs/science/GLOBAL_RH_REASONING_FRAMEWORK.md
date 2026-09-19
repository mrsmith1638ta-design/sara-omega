# SARA-OMEGA Global RH Reasoning Framework

## Purpose

SARA applies the proof discipline developed in the Riemann Hypothesis research
program to every governed reasoning request.

This does **not** mean that every request is mathematically transformed into a
Riemann-Hypothesis problem. Literal zeta, Möbius, Nyman-Beurling, Tail Attack,
or related equations are used only when the request is actually RH-relevant.

The universal framework is the reasoning discipline:

1. establish exact structure before estimating or generalizing;
2. separate proved/verified facts from finite evidence, hypotheses, and blocked
   claims;
3. expose assumptions, unknowns, and proof dependencies;
4. preserve signed or coupled terms long enough to test whether cancellation is
   being discarded;
5. record lossy transformations such as absolute-value bounds, worst-case
   bounds, averaging, or finite-to-infinite promotion;
6. red-team circular reasoning and premises that are already as strong as the
   desired conclusion;
7. reject finite evidence as proof of a universal/asymptotic theorem unless a
   valid transfer argument is attached;
8. cap the conclusion at the strongest independently supported dependency.

## Runtime integration

The integration point is `SaraOmega.solve()`.

Every governed solve request receives an `rh_framework` object immediately
after the problem map is built. The framework is then updated after specialist
evidence, verification, cross-examination, and stress testing.

The framework is included in:

- the semantic judge payload;
- the final `Verdict.rh_framework` field;
- the dual-signed verdict ledger payload;
- the council MAP-stage trace metadata.

The legacy conversational completion path also receives the same framework
instruction before the direct LLM call.

## Domain behavior

For non-RH requests:

- `applied_to_every_request=true`;
- `literal_rh_math=false`;
- SARA uses the proof discipline without injecting irrelevant RH mathematics.

For RH requests:

- `literal_rh_math=true`;
- the same universal discipline applies;
- the dedicated RH science provider may additionally run the full registered
  equations, Tail Attack research objects, and RH proof-status gates.

## Authority boundary

The RH framework is a reasoning layer only.

It cannot:

- override governance;
- increase execution authority;
- bypass authentication or safety controls;
- convert an unsupported claim into a verified claim;
- promote numerical or finite evidence into a theorem.

Governance and authority decisions dominate the framework.

## Required evidence states

The global framework maps verified evidence into bounded reasoning states such
as:

- `PROVED_OR_VERIFIED`
- `CORROBORATED`
- `DISPUTED`
- `STALE`
- `UNSUPPORTED`
- `UNVERIFIABLE`

The final ceiling is recorded as `SUPPORTED`, `QUALIFIED`,
`GOVERNANCE_LIMITED`, or `TRUTH_GATE_LIMITED` according to the evidence and
runtime gates.

## Acceptance requirement

A production build satisfies the universal-framework requirement only if tests
show that:

- trivial requests receive the framework;
- RH requests receive the same framework with literal RH mode enabled;
- governance-blocked requests still receive the framework but cannot use it to
  bypass governance;
- the judge payload contains the framework instruction;
- the durable ledger record contains the framework object.
