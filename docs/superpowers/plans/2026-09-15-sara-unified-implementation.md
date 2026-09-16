# SARA Unified Ecosystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one installable Python 3.12+ SARA runtime that unifies governance, security, evidence, cognition, operations, persistence, API, CLI, and governed recovery behind one canonical `SARAUnified` application.

**Architecture:** A production-oriented modular monolith with strict subsystem contracts. State-changing paths pass through identity, replay, authorization, policy, approval, and audit controls; observational subsystems cannot invent runtime state, and external ROAD/SIOS attestations remain adapter-driven and fail closed when mandatory.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, cryptography, pytest, stdlib HMAC/SHA-256, SQLite local / PostgreSQL-configurable production.

**Spec:** `docs/superpowers/specs/2026-09-15-sara-unified-ecosystem-design.md`

## Global Constraints
- One canonical Python application and entrypoint.
- Default-deny authorization and fail-closed governance/security.
- No autonomous destructive remediation without explicit authority.
- No fake ROAD/SIOS/runtime attestations.
- Observation-backed digital twin state only.
- Tamper-evident audit and signed capability passports.
- Counterfactual analysis must not mutate production state.
- No TODO/TBD/stub execution paths in the release package.

---

### Task 1: Core contracts, configuration, persistence, and audit chain
**Files:** `sara_unified/config.py`, `contracts.py`, `errors.py`, `persistence/db.py`, `evidence/audit.py`, tests.
**Interfaces:** Produce typed request/decision models, application settings, SQLAlchemy engine/session factory, append/verify audit chain.
- [ ] Write failing tests for audit append/verify/tamper detection and settings validation.
- [ ] Run tests and confirm RED.
- [ ] Implement minimal production behavior.
- [ ] Run tests and confirm GREEN.

### Task 2: Security and governance gates
**Files:** `security/*`, `governance/*`, tests.
**Interfaces:** `IdentityVerifier`, `ReplayGuard`, `Authorizer`, `PolicyEngine`, `ApprovalStore`, ROAD/SIOS adapters/contracts.
- [ ] Write failing default-deny, freshness/replay, approval, mandatory-attestation tests.
- [ ] Confirm RED, implement, confirm GREEN.

### Task 3: Evidence fusion and passports
**Files:** `evidence/claims.py`, `provenance.py`, `fusion.py`, `signing.py`, `passports.py`, tests.
**Interfaces:** Structured claims with epistemic status, contradiction-preserving fusion, Ed25519 signing/verification, capability passport verification.
- [ ] Write failing contradiction/signature/tamper tests.
- [ ] Confirm RED, implement, confirm GREEN.

### Task 4: Cognitive engines
**Files:** `cognition/jury.py`, `counterfactual.py`, `gaps.py`, `temporal.py`, `causal.py`, `experiment.py`, tests.
**Interfaces:** Evidence-aware disagreement resolution, isolated scenario simulation, gap derivation, temporal change records, causal/hypothesis plans.
- [ ] Write failing tests proving no majority-only adjudication and no production mutation.
- [ ] Confirm RED, implement, confirm GREEN.

### Task 5: Operations plane and governed recovery
**Files:** `operations/registry.py`, `digital_twin.py`, `observability.py`, `recovery.py`, `incidents.py`, tests.
**Interfaces:** Capability/service registry, observation-backed twin, readiness aggregation, allowlisted recovery registry, incident timelines/blast radius.
- [ ] Write failing tests for verified observations, readiness fail-closed, approval-required recovery, incident containment.
- [ ] Confirm RED, implement, confirm GREEN.

### Task 6: Governed skill registry/compiler
**Files:** `skills/compiler.py`, `skills/registry.py`, tests.
**Interfaces:** Validate typed workflows, enumerate effects/permissions/approval/rollback/tests, register but never auto-activate without policy authorization.
- [ ] Write failing tests for invalid workflows and activation denial.
- [ ] Confirm RED, implement, confirm GREEN.

### Task 7: Unified application, API, CLI, packaging
**Files:** `app.py`, `api/*`, `cli.py`, `__main__.py`, `pyproject.toml`, `README.md`, `Dockerfile`, `.github/workflows/security.yml`, tests.
**Interfaces:** `SARAUnified`, `/health`, `/readyz`, `/v1/*` read/write families, `python -m sara_unified`.
- [ ] Write failing API integration tests including unauthorized mutation rejection.
- [ ] Confirm RED, implement, confirm GREEN.

### Task 8: Release verification and artifact
**Files:** all.
- [ ] Run `pytest -q`.
- [ ] Run compile/import checks.
- [ ] Scan source for TODO/TBD/stub execution markers.
- [ ] Build wheel/sdist if build tooling is available.
- [ ] Produce deterministic ZIP excluding caches and transient DBs.
- [ ] Record SHA-256 in `BUILD-REPORT.md`.
