# Historical Nuclear Fusion Research Algorithm

SARA includes a runnable comparative research laboratory centered on the
algorithm identified as `egyptian-dyadic-bateman-fusion`.

It combines three bounded ideas:

- Egyptian mathematics: repeated doubling and binary decomposition of time
  blocks, inspired by the Rhind mathematical tradition.
- Eighteenth-century mathematics: the linear decay-chain framing associated
  with Laplace-era mathematical physics.
- Nuclear physics: a stable-terminal-nuclide radioactive decay-chain model.

The implementation builds a small Euler transition operator, squares it into
dyadic powers, and composes the powers selected by the binary expansion of the
requested number of blocks. The laboratory solves the same generated inputs
with forward Euler, RK4, the fused method, and a scaled Taylor matrix
exponential reference. It records error, conservation, nonnegativity, runtime,
and bounded Monte Carlo rate uncertainty.

Run it directly from the repository:

```text
python tools/benchmark_historical_nuclear_fusion.py --samples 100 --seed 0

# comparative laboratory
python tools/benchmark_historical_nuclear_fusion.py --laboratory --samples 100 --seed 0 --uncertainty-samples 100
```

The laboratory reports a scoped numerical claim rather than declaring a
general advantage. A claim is `SUPPORTED` only for the generated sample set
when its measured conditions hold; otherwise it is `UNSUPPORTED`.

Madhouse reviews the solver source as part of the benchmark. A broken
candidate is `BLOCKED`; a clean candidate is only `READY_FOR_VERIFICATION`.
Madhouse cannot grant `PASS`, execution authority, promotion authority, or
production authority.

This is numerical and educational research software. It is not a reactor
controller, safety system, weapons model, targeting system, or experimental
validation of nuclear behavior. Its RK4 comparison measures numerical
agreement with another computational method only.
