# SARA Causal-Scope Authority

SARA causal-scope authority authorizes the consequences an action may create,
not merely the command identity used to create them.

## Controls

- Causal finality reconciliation compares the actual downstream effect set with
  the effect set approved before execution.
- Matching command identity does not override a causal mismatch.
- Any unapproved effect, or missing approved effect, quarantines the result.
- Transitive authority revocation follows provenance dependencies forward from
  a compromised source, memory, artifact, or transaction and suspends execution
  authority for descendants.

## Boundary

This control is part of the governed unified fusion layer. It does not grant
production authority, release authority, ROAD PASS, or autonomous repair
authority. It narrows or revokes execution eligibility when observed effects or
provenance dependencies exceed the approved causal envelope.
