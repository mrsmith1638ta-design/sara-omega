# SARA Concentration Governor

SARA-OMEGA V3.2.1 includes a deterministic concentration governor to reduce AI deviation from the user's stated objective. It is designed for code, programming, high-reasoning, and problem-solving workflows where wandering into unrelated narrative should be treated as loss of focus.

The governor computes:

```text
F = 1 - D
D = .34(1-A) + .18S + .16E + .16M + .16R + .12(1-K)
```

Where:

- `F` is the focus score.
- `D` is the deviation score.
- `A` is objective alignment.
- `S` is scope drift.
- `E` is output entropy.
- `M` is action mismatch.
- `R` is risk pressure.
- `K` is constraint coverage.

If `F` falls below the configured threshold, SARA returns:

```text
render_instruction = refocus_before_final
```

## Integration Points

- `GET /concentration/health`
- `POST /concentration/analyze`
- `POST /gpt/action/gateway` with `operation: concentration`
- `POST /gpt/action/gateway` with `operation: solve`, which returns `concentration_governor` beside the verdict and Hawkins Chaos stability vector

## Boundary

The concentration governor can force refocus before rendering, but it cannot approve unsafe content, override truth verification, bypass authorization, or weaken the fail-safe.
