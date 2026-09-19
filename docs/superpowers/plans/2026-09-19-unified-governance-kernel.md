# Unified Governance Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic SARA-OMEGA governance kernel with evidence verification and insurance requirement validation.

**Architecture:** Implement the kernel as a focused standard-library module under `sara_unified.governance`. Keep all execution decisions deterministic and evidence-producing, with tests exercising each decision path.

**Tech Stack:** Python 3.11+, dataclasses, enum, hashlib, hmac, pytest.

**Spec:** `docs/superpowers/specs/2026-09-19-unified-governance-kernel-design.md`

## Global Constraints

Keep execution authority separate from reasoning authority.
Do not weaken governance rules merely to make a test pass.
Use only standard-library dependencies for the new kernel.
Do not assert universal legal insurance requirements; validate only supplied requirement sets.

## Review Focus

Unauthenticated or unauthorized actors must be denied, not escalated.
High risk below quarantine but above policy threshold must escalate and require human approval.
Quarantine-threshold risk must return `QUARANTINE`.
Insurance exclusions and missing verification must fail coverage gates.
Tampered evidence must fail independent verification.

---

### Task 1: Kernel Module

**Files:**
- Create: `sara_unified/governance/unified_kernel.py`
- Modify: `sara_unified/governance/__init__.py`
- Test: `tests/test_unified_governance_kernel.py`

**Interfaces:**
- Produces: `SARAUnifiedGovernanceKernel.evaluate(request, policy, insurance_policy=None, insurance_requirements=None, previous_evidence_hash=None) -> ExecutionEvidence`
- Produces: `IndependentEvidenceVerifier.verify(evidence, signing_key) -> tuple[bool, str]`
- Produces: dataclasses for action requests, policies, coverage requirements, insurance policies, and evidence.

- [ ] Write failing tests for allow, deny, escalation, quarantine, insurance failure, valid evidence verification, and tamper rejection.
- [ ] Run `python -m pytest tests/test_unified_governance_kernel.py -q` and verify the tests fail because the module does not exist.
- [ ] Implement the standard-library governance kernel and package exports.
- [ ] Run `python -m pytest tests/test_unified_governance_kernel.py -q` and verify the tests pass.
- [ ] Run `python -m pytest tests/test_governance.py tests/test_unified_core.py tests/test_unified_governance_kernel.py -q`.

### Task 2: Documentation

**Files:**
- Create: `docs/unified-governance-kernel.md`

**Interfaces:**
- Consumes: public API from `sara_unified.governance.unified_kernel`
- Produces: usage and boundary documentation for repository users.

- [ ] Document runtime gates, decision aggregation, insurance boundary, and evidence verification.
- [ ] Run `python -m pytest tests/test_unified_governance_kernel.py -q` to verify documentation did not affect code behavior.
