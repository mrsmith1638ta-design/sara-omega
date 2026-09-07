# High-Level Truth Gate TDD RED checkpoint

Expected current failures before production implementation:
- `app.science.models` does not yet define ApplicabilityScope, CertaintyLevel, UniversalityStatus, EngineeringState, ScienceClaim, or TruthGateDecision.
- `app.science.truth_gate` does not yet exist.
- Current EDS comparison still exposes architecture-dependent properties as booleans.
- Current HTS comparison still exposes transport-level passive restoring behavior as a boolean.

This checkpoint exists only to document the intended RED state before implementation. CI must confirm the failures before production code is added.
