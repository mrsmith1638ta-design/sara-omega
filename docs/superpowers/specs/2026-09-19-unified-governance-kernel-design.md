# Unified Governance Kernel Design

## Goal

Add a deterministic SARA-OMEGA governance kernel that evaluates requested AI or agent actions before execution, produces tamper-evident evidence, and keeps reasoning authority separate from execution authority.

## Scope

The kernel lives inside `sara_unified.governance` and uses only the Python standard library. It does not call an LLM, provider, broker, insurer, or external service. Insurance logic validates supplied policy evidence against an explicit requirement set; it does not decide what coverage is legally required.

## Runtime Gates

Each request is evaluated through identity, authority, policy, state transition, provenance, counterfactual risk, human approval, and insurance coverage gates. Hard failures deny execution. Quarantine-threshold risk quarantines execution. Review gates escalate execution. Only when every required gate passes does the kernel allow execution.

## Evidence

Every evaluation returns `ExecutionEvidence` containing the decision, gate results, risk score and factors, request digest, optional previous evidence hash, evidence hash, and HMAC signature. The independent verifier recomputes the evidence hash and signature from the evidence payload and rejects any tampering.

## Tests

Tests cover allow, deny, escalation, quarantine, insurance failure, evidence verification, and evidence tampering.
