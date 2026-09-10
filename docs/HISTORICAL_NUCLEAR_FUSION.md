# Historical Nuclear Fusion Research Algorithm

SARA includes a runnable research algorithm identified as
`egyptian-dyadic-bateman-fusion`.

It combines three bounded ideas:

- Egyptian mathematics: repeated doubling and binary decomposition of time
  blocks, inspired by the Rhind mathematical tradition.
- Eighteenth-century mathematics: the linear decay-chain framing associated
  with Laplace-era mathematical physics.
- Nuclear physics: a stable-terminal-nuclide radioactive decay-chain model.

The implementation builds a small Euler transition operator, squares it into
dyadic powers, and composes the powers selected by the binary expansion of the
requested number of blocks. It is compared against a fixed-step RK4 reference
on generated inputs.

Run it directly from the repository:

```text
python tools/benchmark_historical_nuclear_fusion.py --samples 100 --seed 0
```

Madhouse reviews the solver source as part of the benchmark. A broken
candidate is `BLOCKED`; a clean candidate is only `READY_FOR_VERIFICATION`.
Madhouse cannot grant `PASS`, execution authority, promotion authority, or
production authority.

This is numerical and educational research software. It is not a reactor
controller, safety system, weapons model, targeting system, or experimental
validation of nuclear behavior. Its RK4 comparison measures numerical
agreement with another computational method only.
