# SARA OMEGA Voice 1.1A Accessibility API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a limited OAuth-authenticated accessibility voice API with durable entitlement, tenant isolation, rate limits, privacy controls, abuse controls, and a separate Voice 1.1A production evidence chain while preserving Voice 1.0 and Voice 1.1.

**Architecture:** Add a dedicated encrypted SQLite access store and FastAPI router under `app/`. The router resolves the existing OAuth principal, applies server-owned tenant and entitlement policy, reserves durable user/tenant quotas, and invokes the accepted `sara_unified.voice` job engine through a Voice 1.1A-only manager. Owner Voice 1.1 routes remain behaviorally unchanged, and Voice 1.1A requires two independent release flags.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLite WAL, AES-GCM from `cryptography`, pytest, existing OAuth identity store, existing governed Piper client, Railway, ROAD/SISO/Madhouse gates.

**Spec:** `docs/superpowers/specs/2026-09-17-voice-1-1a-accessibility-api-design.md`

## Global Constraints

- Preserve Voice 1.0 commit `30c1f606092b6d4043413a185d8e0ac8d3458de2`, deployment `08bba7e1-9b51-4656-a8a2-6e4b3cf32575`, and every accepted Voice 1.0 evidence file unchanged.
- Preserve Voice 1.1 commit `3b8948894cf7a93472a7289079ae41ba99c2a096`, SARA deployment `ffa3e879-a610-4d57-885b-e76de546fcf5`, Piper deployment `0a831729-4f80-4981-ae17-a888108ef82e`, and accepted Voice 1.1 evidence unchanged.
- Do not change the paths, authentication, or response contract of owner-only Voice 1.1 routes.
- Voice 1.1A routes require both `SARA_VOICE_1_1A_ENABLED=true` and `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=true`; either false yields `404`.
- User routes accept only OAuth bearer tokens with `sara.voice.accessibility`; owner, action, and test tokens are not user credentials.
- Resolve user and tenant identity from durable server records only. Strict request models forbid unknown fields.
- Keep Piper isolated in `voice_service/`; do not expose model selection, paths, URLs, tokens, pronunciation rules, or raw Piper controls.
- Keep transcript preservation false by default; encrypt opted-in transcripts and enforce retention before returning plaintext.
- Persist Voice 1.1A state only under the existing `SARA_DATA_DIR` volume. Do not create cloud resources.
- Write only new `sara-omega-voice-1-1a-*` evidence artifacts; never extend older capsules in place.
- Follow RED -> GREEN -> focused verification -> adversarial review -> ROAD blocker check -> commit for every task. Do not begin the next task if any checkpoint fails.
- Execute inline in the current task unless the owner explicitly changes the execution mode.

## Execution Prerequisite

Before Task 1, use the `superpowers:using-git-worktrees` skill to create `.worktrees/voice-1-1a-accessibility` from the approved spec/plan commit. Verify `.worktrees` is ignored, install no new dependencies, and establish a clean baseline with:

```powershell
pytest -q
python -m compileall -q main.py app sara_unified voice_service tools
```

Both commands must exit zero before Task 1. All implementation, commits, and pre-deployment verification occur in that worktree.

## File Map

- `sara_unified/config.py`: validated Voice 1.1A flags and quota configuration.
- `sara_unified/api/schemas.py`: strict Voice 1.1A request models only.
- `app/user_identity.py`: read-only account lookup for owner entitlement administration.
- `app/voice_accessibility.py`: durable tenants, memberships, entitlements, preferences, ownership, transcripts, quotas, leases, and audit records.
- `app/voice_accessibility_http.py`: dual gate, OAuth authorization, owner administration, preferences, jobs, audio, transcript, and receipt routes.
- `app/enterprise_runtime.py`: register the Voice 1.1A router.
- `main.py`: remove only the superseded gated accessibility stub after the new router proves identical fail-closed behavior; owner Voice 1.1 handlers stay unchanged.
- `tests/test_voice_1_1a_config.py`: settings and strict schema tests.
- `tests/test_voice_1_1a_store.py`: persistence, encryption, isolation, quota, concurrency, and restart tests.
- `tests/test_voice_1_1a_api.py`: credential, entitlement, tenant, route, privacy, and synthesis tests.
- `tests/test_voice_1_1a_adversarial.py`: cross-tenant, quota-evasion, identifier-probing, and secret-leak tests.
- `tests/test_voice_1_1a_tools.py`: acceptance evidence builder tests.
- `tools/voice_1_1a_acceptance_probe.py`: deterministic evidence assembly and immutable-baseline hashing.
- `docs/voice-1-1a-production-acceptance.md`: exact deployment and certification runbook.
- `chatgpt-gpt-action.yaml`: document the new OAuth scope and accessibility routes without secrets.
- `README.md`: release boundary and disabled-by-default configuration.

---

### Task 1: Release Configuration And Strict API Contracts

**Files:**
- Modify: `sara_unified/config.py`
- Modify: `sara_unified/api/schemas.py`
- Create: `tests/test_voice_1_1a_config.py`

**Interfaces:**
- Consumes: existing `Settings.from_env()` and Pydantic v2.
- Produces: `Settings.voice_1_1a_enabled`, validated Voice 1.1A quota fields, `VoiceAccessibilityJobRequest`, `VoiceAccessibilityPreferencesRequest`, and `VoiceAccessibilityEntitlementRequest`.

- [ ] **Step 1: Write failing configuration and schema tests**

```python
from pydantic import ValidationError
import pytest

from sara_unified.api.schemas import (
    VoiceAccessibilityEntitlementRequest,
    VoiceAccessibilityJobRequest,
    VoiceAccessibilityPreferencesRequest,
)
from sara_unified.config import Settings


def test_voice_1_1a_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SARA_VOICE_1_1A_ENABLED", raising=False)
    assert Settings.from_env().voice_1_1a_enabled is False


def test_voice_1_1a_limits_are_positive(monkeypatch):
    monkeypatch.setenv("SARA_VOICE_1_1A_USER_JOBS_PER_MINUTE", "0")
    with pytest.raises(ValueError, match="SARA_VOICE_1_1A_USER_JOBS_PER_MINUTE"):
        Settings.from_env()


def test_accessibility_job_rejects_caller_owned_tenant_and_unknown_controls():
    with pytest.raises(ValidationError):
        VoiceAccessibilityJobRequest.model_validate(
            {"text": "Hello.", "tenant_id": "forged", "length_scale": 0.5}
        )


def test_accessibility_preferences_enforce_retention_contract():
    valid = VoiceAccessibilityPreferencesRequest(
        speech_rate="slower", preserve_transcript=True, transcript_retention_seconds=3600
    )
    assert valid.transcript_retention_seconds == 3600
    with pytest.raises(ValidationError):
        VoiceAccessibilityPreferencesRequest(
            speech_rate="normal", preserve_transcript=False, transcript_retention_seconds=3600
        )


def test_entitlement_request_forbids_tenant_selection():
    with pytest.raises(ValidationError):
        VoiceAccessibilityEntitlementRequest.model_validate(
            {"public_user_id": "SARA-U-ABC", "tenant_id": "forged"}
        )
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `pytest -q tests/test_voice_1_1a_config.py`

Expected: import failures for the three request models and missing `voice_1_1a_enabled`.

- [ ] **Step 3: Implement validated settings and strict request models**

Add these settings with defaults:

```python
voice_1_1a_enabled: bool = False
voice_1_1a_user_jobs_per_minute: int = 6
voice_1_1a_user_jobs_per_day: int = 100
voice_1_1a_user_characters_per_day: int = 100_000
voice_1_1a_tenant_jobs_per_minute: int = 20
voice_1_1a_tenant_jobs_per_day: int = 500
voice_1_1a_tenant_characters_per_day: int = 500_000
voice_1_1a_user_concurrency: int = 1
voice_1_1a_tenant_concurrency: int = 4
voice_1_1a_lease_seconds: int = 60
```

Parse matching `SARA_VOICE_1_1A_*` environment variables in `Settings.from_env()` and raise `ValueError("<NAME> must be positive")` for any value below 1.

Add strict Pydantic models:

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VoiceAccessibilityJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)
    speech_rate: Literal["slower", "normal", "faster"] | None = None
    preserve_transcript: bool | None = None


class VoiceAccessibilityPreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speech_rate: Literal["slower", "normal", "faster"]
    preserve_transcript: bool
    transcript_retention_seconds: Literal[0, 900, 3600, 86400]

    @model_validator(mode="after")
    def validate_retention(self):
        if self.preserve_transcript != (self.transcript_retention_seconds > 0):
            raise ValueError("transcript retention does not match preservation choice")
        return self


class VoiceAccessibilityEntitlementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_user_id: str = Field(pattern=r"^SARA-U-[A-F0-9]{12}$")
    expires_at: datetime | None = None
```

- [ ] **Step 4: Verify GREEN and regression safety**

Run: `pytest -q tests/test_voice_1_1a_config.py tests/test_production_voice_1_1.py tests/test_voice_1_1_core.py`

Expected: all selected tests pass.

- [ ] **Step 5: Run checkpoint review and commit**

Run: `git diff --check`

Inspect: `git diff -- sara_unified/config.py sara_unified/api/schemas.py tests/test_voice_1_1a_config.py`

ROAD: call the blocking-dependencies gate and require `status=PASS` with an empty blocker list.

```bash
git add sara_unified/config.py sara_unified/api/schemas.py tests/test_voice_1_1a_config.py
git commit -m "feat: define Voice 1.1A release contracts"
```

---

### Task 2: Durable Tenant, Entitlement, Preference, Ownership, And Transcript Store

**Files:**
- Create: `app/voice_accessibility.py`
- Modify: `app/user_identity.py`
- Create: `tests/test_voice_1_1a_store.py`

**Interfaces:**
- Consumes: `derive_secret_key(context, required=True)`, `AESGCM`, `UserIdentityStore`.
- Produces: `VoiceAccessibilityStore.from_env()`, `VoiceAccessContext`, `VoicePreferences`, `get_account_by_public_id()`, entitlement and privacy methods.

- [ ] **Step 1: Write failing persistence and isolation tests**

```python
from datetime import datetime, timedelta, timezone
import pytest

from app.voice_accessibility import VoiceAccessRejected, VoiceAccessibilityStore


def test_grant_creates_server_owned_individual_tenant(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    granted = store.grant_entitlement("00000000-0000-4000-8000-000000000001", "owner")
    resolved = store.resolve_access("00000000-0000-4000-8000-000000000001")
    assert resolved.tenant_id == granted.tenant_id
    assert resolved.entitlement_status == "ACTIVE"


def test_revocation_is_immediate_and_survives_restart(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    user_uuid = "00000000-0000-4000-8000-000000000001"
    first = VoiceAccessibilityStore.from_env(required=True)
    first.grant_entitlement(user_uuid, "owner")
    first.revoke_entitlement(user_uuid, "owner")
    second = VoiceAccessibilityStore.from_env(required=True)
    with pytest.raises(VoiceAccessRejected, match="entitlement_inactive"):
        second.resolve_access(user_uuid)


def test_preferences_and_jobs_are_user_and_tenant_isolated(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    user_a = "00000000-0000-4000-8000-000000000001"
    user_b = "00000000-0000-4000-8000-000000000002"
    access_a = store.grant_entitlement(user_a, "owner")
    access_b = store.grant_entitlement(user_b, "owner")
    store.record_job("job-a", access_a, "a" * 64, preserve_transcript=False)
    assert store.owns_job("job-a", access_a) is True
    assert store.owns_job("job-a", access_b) is False


def test_transcript_is_encrypted_and_expiry_enforced(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    access = store.grant_entitlement("00000000-0000-4000-8000-000000000001", "owner")
    store.record_job("job-a", access, "a" * 64, preserve_transcript=True)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=900)
    store.save_transcript("job-a", access, "Private sentence", expiry)
    assert store.load_transcript("job-a", access) == "Private sentence"
    assert b"Private sentence" not in (tmp_path / "sara_voice_accessibility.db").read_bytes()
    assert store.load_transcript("job-a", access, now=expiry + timedelta(seconds=1)) is None
```

Add `configure_voice_store()` in the test file to set `SARA_DATA_DIR` and a fixed 32-byte `SARA_MEMORY_KEY_HEX`.

- [ ] **Step 2: Run the store tests and confirm RED**

Run: `pytest -q tests/test_voice_1_1a_store.py`

Expected: `ModuleNotFoundError` for `app.voice_accessibility`.

- [ ] **Step 3: Implement the store schema and access records**

Define:

```python
@dataclass(frozen=True)
class VoiceAccessContext:
    user_uuid: str
    tenant_id: str
    entitlement_status: str


@dataclass(frozen=True)
class VoicePreferences:
    speech_rate: str = "normal"
    preserve_transcript: bool = False
    transcript_retention_seconds: int = 0


class VoiceAccessRejected(RuntimeError):
    pass
```

Implement these exact `VoiceAccessibilityStore` signatures: `from_env(cls, *, required: bool = True) -> VoiceAccessibilityStore | None`; `grant_entitlement(self, user_uuid: str, actor: str, expires_at: datetime | None = None) -> VoiceAccessContext`; `revoke_entitlement(self, user_uuid: str, actor: str) -> None`; `resolve_access(self, user_uuid: str, *, now: datetime | None = None) -> VoiceAccessContext`; `get_preferences(self, access: VoiceAccessContext) -> VoicePreferences`; `set_preferences(self, access: VoiceAccessContext, preferences: VoicePreferences) -> VoicePreferences`; `record_job(self, job_id: str, access: VoiceAccessContext, source_digest: str, *, preserve_transcript: bool) -> None`; `owns_job(self, job_id: str, access: VoiceAccessContext) -> bool`; `save_transcript(self, job_id: str, access: VoiceAccessContext, text: str, expires_at: datetime) -> None`; `load_transcript(self, job_id: str, access: VoiceAccessContext, *, now: datetime | None = None) -> str | None`; and `purge_user_data(self, user_uuid: str, actor: str) -> dict[str, int]`.

Create the exact tables from the design. Hash ownership identifiers with HMAC-SHA256 using `derive_secret_key("voice-1-1a-ownership")`; encrypt transcript bytes using AES-GCM and `derive_secret_key("voice-1-1a-transcripts")`, with `job_id` plus hashed ownership as associated data. Use `BEGIN IMMEDIATE` for grants, revocations, job ownership writes, and purges.

Add this read-only identity method:

```python
def get_account_by_public_id(self, public_user_id: str) -> AccountRecord | None:
    with closing(self._connect()) as conn:
        row = conn.execute("SELECT * FROM users WHERE public_user_id=?", (public_user_id,)).fetchone()
    return self._account_from_row(row) if row is not None else None
```

- [ ] **Step 4: Verify GREEN, restart behavior, and older identity tests**

Run: `pytest -q tests/test_voice_1_1a_store.py tests/test_user_oauth.py tests/test_user_identity_security.py`

Expected: all selected tests pass; the database byte scan cannot find transcript plaintext.

- [ ] **Step 5: Run checkpoint review and commit**

Run: `git diff --check`

Inspect the SQLite transaction boundaries, HMAC comparisons, AES-GCM AAD, expiry checks, and exception redaction.

ROAD: require no blocking dependencies.

```bash
git add app/voice_accessibility.py app/user_identity.py tests/test_voice_1_1a_store.py
git commit -m "feat: add Voice 1.1A access persistence"
```

---

### Task 3: Durable Quotas And Concurrency Leases

**Files:**
- Modify: `app/voice_accessibility.py`
- Modify: `tests/test_voice_1_1a_store.py`

**Interfaces:**
- Consumes: `VoiceAccessContext` and validated Voice 1.1A settings.
- Produces: `VoiceUsageLimits`, `VoiceUsageReservation`, `reserve_usage()`, `release_lease()`.

- [ ] **Step 1: Add failing quota, race, and restart tests**

```python
def test_atomic_user_and_tenant_limits_cannot_be_bypassed(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    store = VoiceAccessibilityStore.from_env(required=True)
    access = store.grant_entitlement(USER_A, "owner")
    limits = VoiceUsageLimits(user_jobs_per_minute=1, user_jobs_per_day=2,
        user_characters_per_day=20, tenant_jobs_per_minute=2,
        tenant_jobs_per_day=3, tenant_characters_per_day=30,
        user_concurrency=1, tenant_concurrency=2, lease_seconds=60)
    reservation = store.reserve_usage(access, characters=5, limits=limits)
    with pytest.raises(VoiceRateLimitRejected, match="user_concurrency"):
        store.reserve_usage(access, characters=5, limits=limits)
    store.release_lease(reservation.lease_id)
    with pytest.raises(VoiceRateLimitRejected, match="user_jobs_per_minute"):
        store.reserve_usage(access, characters=5, limits=limits)


def test_quota_survives_restart_and_expired_lease_does_not(tmp_path, monkeypatch):
    configure_voice_store(monkeypatch, tmp_path)
    first = VoiceAccessibilityStore.from_env(required=True)
    access = first.grant_entitlement(USER_A, "owner")
    reservation = first.reserve_usage(access, characters=5, limits=LIMITS, now=NOW)
    second = VoiceAccessibilityStore.from_env(required=True)
    with pytest.raises(VoiceRateLimitRejected):
        second.reserve_usage(access, characters=5, limits=LIMITS, now=NOW)
    second.reserve_usage(access, characters=5, limits=LIMITS, now=NOW + timedelta(seconds=61))
```

Add a `ThreadPoolExecutor` test that starts two simultaneous reservations against a one-job minute limit and asserts exactly one succeeds.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `pytest -q tests/test_voice_1_1a_store.py -k "limit or quota or lease or atomic"`

Expected: import or attribute failures for quota types and methods.

- [ ] **Step 3: Implement atomic reservations**

```python
@dataclass(frozen=True)
class VoiceUsageLimits:
    user_jobs_per_minute: int
    user_jobs_per_day: int
    user_characters_per_day: int
    tenant_jobs_per_minute: int
    tenant_jobs_per_day: int
    tenant_characters_per_day: int
    user_concurrency: int
    tenant_concurrency: int
    lease_seconds: int


@dataclass(frozen=True)
class VoiceUsageReservation:
    lease_id: str
    accepted_at: str


class VoiceRateLimitRejected(RuntimeError):
    def __init__(self, reason_code: str, retry_after: int | None = None):
        self.reason_code = reason_code
        self.retry_after = retry_after
        super().__init__(reason_code)
```

Implement `reserve_usage(access, characters, limits, now=None)` in one `BEGIN IMMEDIATE` transaction:

1. Delete expired leases.
2. Count active user and tenant leases.
3. Reject concurrency before incrementing usage.
4. Read UTC minute and day windows for hashed user and tenant subjects.
5. Reject the first exceeded limit with one of: `user_jobs_per_minute`, `user_jobs_per_day`, `user_characters_per_day`, `tenant_jobs_per_minute`, `tenant_jobs_per_day`, `tenant_characters_per_day`.
6. Increment all four windows and insert the lease atomically.

Implement idempotent `release_lease(lease_id)` as a bounded delete.

- [ ] **Step 4: Verify GREEN and transaction integrity**

Run: `pytest -q tests/test_voice_1_1a_store.py`

Expected: all tests pass, including concurrent admission and restart persistence.

- [ ] **Step 5: Run checkpoint review and commit**

Run: `git diff --check`

Inspect: no quota key uses IP, session ID, public user ID, or caller input; failed synthesis still consumes accepted quota; lease release is separate from usage rollback.

ROAD: require no blocking dependencies.

```bash
git add app/voice_accessibility.py tests/test_voice_1_1a_store.py
git commit -m "feat: enforce durable Voice 1.1A quotas"
```

---

### Task 4: Dual Gate, OAuth Scope, Preferences, And Owner Administration

**Files:**
- Create: `app/voice_accessibility_http.py`
- Modify: `app/enterprise_runtime.py`
- Modify: `main.py`
- Create: `tests/test_voice_1_1a_api.py`

**Interfaces:**
- Consumes: `OAuthPrincipal`, `UserIdentityStore`, `VoiceAccessibilityStore`, strict schemas, `RuntimeFailSafe`.
- Produces: registered `voice_accessibility_router`, owner entitlement routes, user preference routes, shared authorization helpers.

- [ ] **Step 1: Write failing gate and credential-boundary tests**

```python
def test_each_release_flag_fails_closed(monkeypatch):
    configure_runtime(monkeypatch, enabled=False, public=True)
    assert client.get("/v1/accessibility/voice/preferences").status_code == 404
    configure_runtime(monkeypatch, enabled=True, public=False)
    assert client.get("/v1/accessibility/voice/preferences").status_code == 404


def test_user_route_requires_oauth_scope_and_entitlement(monkeypatch, tmp_path):
    principal, token = provision_oauth_user(monkeypatch, tmp_path, scope="sara.solve")
    configure_runtime(monkeypatch, enabled=True, public=True)
    assert client.get(PREFERENCES, headers=bearer(token)).status_code == 403
    token = issue_token(principal, scope="sara.voice.accessibility")
    assert client.get(PREFERENCES, headers=bearer(token)).status_code == 403
    grant_entitlement(principal.user_uuid)
    assert client.get(PREFERENCES, headers=bearer(token)).status_code == 200


def test_owner_action_and_test_tokens_are_not_oauth_user_credentials(monkeypatch):
    configure_runtime(monkeypatch, enabled=True, public=True)
    for token in ("owner-token", "action-token", "test-token"):
        assert client.get(PREFERENCES, headers=bearer(token)).status_code == 401


def test_only_owner_can_grant_and_revoke_entitlement(monkeypatch, tmp_path):
    account = provision_account(monkeypatch, tmp_path)
    denied = client.post(ENTITLEMENTS, headers=action_headers(), json={"public_user_id": account.public_user_id})
    granted = client.post(ENTITLEMENTS, headers=owner_headers(), json={"public_user_id": account.public_user_id})
    revoked = client.post(f"{ENTITLEMENTS}/{account.public_user_id}/revoke", headers=owner_headers())
    assert denied.status_code == 403
    assert granted.status_code == 200
    assert revoked.status_code == 200


def test_owner_can_read_entitlement_and_purge_only_voice_user_data(monkeypatch, tmp_path):
    account = provision_account(monkeypatch, tmp_path)
    client.post(ENTITLEMENTS, headers=owner_headers(), json={"public_user_id": account.public_user_id})
    status = client.get(f"{ENTITLEMENTS}/{account.public_user_id}", headers=owner_headers())
    purged = client.delete(f"/admin/voice-accessibility/data/{account.public_user_id}", headers=owner_headers())
    assert status.status_code == 200
    assert status.json()["status"] == "ACTIVE"
    assert purged.status_code == 200
    assert set(purged.json()) == {"preferences_deleted", "transcripts_deleted"}
```

- [ ] **Step 2: Run API tests and confirm RED**

Run: `pytest -q tests/test_voice_1_1a_api.py -k "flag or scope or entitlement or owner or preference"`

Expected: Voice 1.1A routes remain absent or only the old gated POST exists.

- [ ] **Step 3: Implement the shared gateway and non-synthesis routes**

Create helpers with these exact signatures: `_require_release() -> Settings`; `_principal(request: Request) -> OAuthPrincipal`; `_require_voice_scope(principal: OAuthPrincipal) -> None`; `_access(principal: OAuthPrincipal) -> VoiceAccessContext`; `_owner(request: Request) -> None`; and `_checkpoint(operation: str, event: FailSafeEvent, *, actor_hash: str) -> None`.

`_require_release()` reads `Settings.from_env()` and returns `404` unless both flags and Voice 1.1 are enabled. `_principal()` accepts a bounded Bearer value and resolves it only through `UserIdentityStore.resolve_access_token()`. `_require_voice_scope()` splits the accepted principal scope and requires exact membership. `_access()` resolves the principal's internal UUID through `VoiceAccessibilityStore.resolve_access()`. `_owner()` uses the existing owner token boundary without granting owner authority to user routes. `_checkpoint()` records only operation and actor hash and maps fail-safe errors to bounded `503` responses.

Register:

```python
@router.post("/admin/voice-accessibility/entitlements")
@router.get("/admin/voice-accessibility/entitlements/{public_user_id}")
@router.post("/admin/voice-accessibility/entitlements/{public_user_id}/revoke")
@router.delete("/admin/voice-accessibility/data/{public_user_id}")
@router.get("/v1/accessibility/voice/preferences")
@router.put("/v1/accessibility/voice/preferences")
```

Owner administration resolves `public_user_id` through `get_account_by_public_id()` and never accepts tenant selection. Preferences derive their user and tenant from `_access()`.

Include the router from `app/enterprise_runtime.py`. Remove only `accessibility_voice_jobs_gated()` from `main.py` after the new router returns the same `404` while disabled. Do not edit the four owner Voice 1.1 handlers.

- [ ] **Step 4: Verify GREEN and Voice 1.1 regression safety**

Run: `pytest -q tests/test_voice_1_1a_api.py tests/test_production_voice_1_1.py tests/test_user_gateway.py tests/test_user_identity_http.py`

Expected: all selected tests pass; disabled accessibility POST still returns `404`.

- [ ] **Step 5: Run checkpoint review and commit**

Run: `git diff --check`

Inspect every route for release gate before authentication, OAuth-only user identity, scope before entitlement, fail-safe before mutation, and bounded public errors.

ROAD: require no blocking dependencies.

```bash
git add app/voice_accessibility_http.py app/enterprise_runtime.py main.py tests/test_voice_1_1a_api.py
git commit -m "feat: add Voice 1.1A access gateway"
```

---

### Task 5: Entitled Speech Jobs, Audio, Transcript, Stop, And Receipts

**Files:**
- Modify: `app/voice_accessibility.py`
- Modify: `app/voice_accessibility_http.py`
- Modify: `tests/test_voice_1_1a_api.py`
- Modify: `tests/test_voice_1_1a_store.py`

**Interfaces:**
- Consumes: `VoiceJobManager`, `PiperVoiceClient`, `VoiceUsageLimits`, ownership and transcript methods.
- Produces: six user-facing job routes and access-envelope receipt digests.

- [ ] **Step 1: Write failing end-to-end route tests with a fake Piper client**

```python
def test_entitled_user_can_speak_and_fetch_private_audio(monkeypatch, tmp_path):
    token, fake = provision_entitled_voice_user(monkeypatch, tmp_path)
    created = client.post(JOBS, headers=bearer(token), json={"text": "First. Second."})
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    segment_id = created.json()["segments"][0]["segment_id"]
    audio = client.get(f"{JOBS}/{job_id}/segments/{segment_id}/audio", headers=bearer(token))
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/wav")
    assert audio.headers["cache-control"] == "private, no-store"
    assert fake.calls == 2


def test_cross_tenant_job_audio_stop_transcript_and_receipts_are_hidden(monkeypatch, tmp_path):
    token_a, _ = provision_entitled_voice_user(monkeypatch, tmp_path, user="a")
    token_b, _ = provision_entitled_voice_user(monkeypatch, tmp_path, user="b")
    created = client.post(JOBS, headers=bearer(token_a), json={"text": "Private.", "preserve_transcript": True})
    job_id = created.json()["job_id"]
    segment_id = created.json()["segments"][0]["segment_id"]
    paths = [
        f"{JOBS}/{job_id}", f"{JOBS}/{job_id}/receipts",
        f"{JOBS}/{job_id}/transcript", f"{JOBS}/{job_id}/segments/{segment_id}/audio",
    ]
    assert all(client.get(path, headers=bearer(token_b)).status_code == 404 for path in paths)
    assert client.post(f"{JOBS}/{job_id}/stop", headers=bearer(token_b)).status_code == 404


def test_lease_releases_on_piper_failure_but_usage_remains(monkeypatch, tmp_path):
    token, fake = provision_entitled_voice_user(monkeypatch, tmp_path)
    fake.error = RuntimeError("private renderer detail")
    failed = client.post(JOBS, headers=bearer(token), json={"text": "Fail safely."})
    assert failed.status_code == 502
    assert "private renderer detail" not in failed.text
    assert active_lease_count() == 0
    assert user_job_usage() == 1
```

Add tests for preference fallback, explicit rate override, transcript expiry, immediate entitlement revocation, `429` reason codes, `Retry-After`, `409` concurrency, strict `422`, idempotent stop, and receipt access-envelope digests that omit raw identifiers.

- [ ] **Step 2: Run speech route tests and confirm RED**

Run: `pytest -q tests/test_voice_1_1a_api.py -k "speak or audio or transcript or receipt or quota or lease or cross_tenant"`

Expected: missing route failures.

- [ ] **Step 3: Implement the Voice 1.1A job adapter and routes**

Create a module-local manager accessor that constructs `PiperVoiceClient` from validated settings and passes it to the accepted `VoiceJobManager`. Keep it separate from `_voice_1_1_job_manager` so no owner job state or route behavior changes.

Register:

```python
@router.post("/v1/accessibility/voice/jobs")
@router.get("/v1/accessibility/voice/jobs/{job_id}")
@router.post("/v1/accessibility/voice/jobs/{job_id}/stop")
@router.get("/v1/accessibility/voice/jobs/{job_id}/segments/{segment_id}/audio")
@router.get("/v1/accessibility/voice/jobs/{job_id}/receipts")
@router.get("/v1/accessibility/voice/jobs/{job_id}/transcript")
```

Creation order is exact: release -> OAuth -> scope -> entitlement -> preferences -> validate -> reserve usage -> fail-safe checkpoint -> synthesize -> record ownership/receipt envelope -> optionally encrypt transcript -> release lease in `finally`.

Add exact store methods `record_receipt_envelope(self, job_id: str, access: VoiceAccessContext, receipt_ids: list[str]) -> str`, `receipt_envelope_digest(self, job_id: str, access: VoiceAccessContext) -> str | None`, and `mark_job_status(self, job_id: str, access: VoiceAccessContext, status: str, *, stopped: bool = False) -> None`.

The envelope digest is SHA-256 over canonical JSON containing job ID, hashed user, hashed tenant, source digest, and ordered receipt IDs. Return it without its preimage.

Map expected failures to the spec's `401`, `403`, `404`, `409`, `422`, `429`, `502`, and `503` responses. Set `Cache-Control: private, no-store` on audio, transcript, preferences, and receipts.

- [ ] **Step 4: Verify GREEN across Voice 1.1A and accepted voice behavior**

Run: `pytest -q tests/test_voice_1_1a_api.py tests/test_voice_1_1a_store.py tests/test_production_voice_1_1.py tests/test_voice_1_1_jobs.py tests/test_voice_synthesis.py`

Expected: all selected tests pass.

- [ ] **Step 5: Run checkpoint review and commit**

Run: `git diff --check`

Inspect identifier lookup paths, `finally` lease release, transcript encryption, no-store headers, audio segment indexing, secret redaction, and unchanged owner handlers.

ROAD: require no blocking dependencies.

```bash
git add app/voice_accessibility.py app/voice_accessibility_http.py tests/test_voice_1_1a_api.py tests/test_voice_1_1a_store.py
git commit -m "feat: expose entitled Voice 1.1A speech"
```

---

### Task 6: Adversarial Suite And Acceptance Evidence Builder

**Files:**
- Create: `tests/test_voice_1_1a_adversarial.py`
- Create: `tests/test_voice_1_1a_tools.py`
- Create: `tools/voice_1_1a_acceptance_probe.py`

**Interfaces:**
- Consumes: live-probe result dictionaries and immutable baseline paths.
- Produces: `build_voice_1_1a_evidence()` and a focused adversarial certification suite.

- [ ] **Step 1: Write failing evidence-builder and adversarial tests**

```python
def test_evidence_hashes_both_immutable_baselines_without_mutation(tmp_path):
    from tools.voice_1_1a_acceptance_probe import build_voice_1_1a_evidence
    voice_1_0 = tmp_path / "voice-1-0.json"
    voice_1_1 = tmp_path / "voice-1-1.json"
    voice_1_0.write_text("v1.0", encoding="utf-8")
    voice_1_1.write_text("v1.1", encoding="utf-8")
    evidence = build_voice_1_1a_evidence(
        voice_1_0_paths=[str(voice_1_0)], voice_1_1_paths=[str(voice_1_1)],
        source_commit_sha="a" * 40, sara_deployment_id="sara-deploy",
        piper_deployment_id="piper-deploy", transaction={"audio_sha256": "b" * 64},
        entitlement={}, isolation={}, limits={}, privacy={}, restart={}, road={"status": "PASS"},
    )
    assert evidence["evidence_type"] == "sara-omega-voice-1-1a-acceptance"
    assert evidence["immutable_baselines"]["voice_1_0"][0]["sha256"]
    assert evidence["records_sensitive_values"] is False
    assert voice_1_0.read_text(encoding="utf-8") == "v1.0"
```

Adversarial tests must exercise: forged tenant/body fields, action/test/owner credential confusion, cross-tenant object access for every route, revoked entitlement reuse, minute/day/character quota evasion via session/header changes, concurrent admission, transcript DB/log/response plaintext scans, receipt enumeration, and renderer exception redaction.

- [ ] **Step 2: Run the new tests and confirm RED**

Run: `pytest -q tests/test_voice_1_1a_tools.py tests/test_voice_1_1a_adversarial.py`

Expected: missing evidence module and any uncovered adversarial behavior fail.

- [ ] **Step 3: Implement deterministic evidence assembly and close discovered gaps**

Implement `build_voice_1_1a_evidence(*, voice_1_0_paths: list[str], voice_1_1_paths: list[str], source_commit_sha: str, sara_deployment_id: str, piper_deployment_id: str, transaction: dict, entitlement: dict, isolation: dict, limits: dict, privacy: dict, restart: dict, road: dict, sensitive_values: list[str] | None = None) -> dict`.

Sort baseline paths before hashing, record path plus SHA-256 only, require 40 lowercase hexadecimal commit characters and nonempty deployment IDs, and recursively reject keys or string values containing bearer credentials, known token names, private service URLs, raw UUIDs, or transcript text supplied in a `sensitive_values` validation list.

For each adversarial failure discovered, add or retain the smallest reproducing test before changing production code, then rerun RED and GREEN for that specific test.

- [ ] **Step 4: Verify GREEN and run the complete voice/security slice**

Run: `pytest -q tests/test_voice_1_1a_tools.py tests/test_voice_1_1a_adversarial.py tests/test_voice_1_1a_api.py tests/test_voice_1_1a_store.py tests/test_production_voice_1_1.py tests/test_user_oauth.py tests/test_user_identity_security.py`

Expected: all selected tests pass.

- [ ] **Step 5: Run checkpoint review and commit**

Run: `git diff --check`

Inspect evidence recursively for secret names/values and verify all older evidence paths are read-only inputs.

ROAD: require no blocking dependencies.

```bash
git add tools/voice_1_1a_acceptance_probe.py tests/test_voice_1_1a_tools.py tests/test_voice_1_1a_adversarial.py app/voice_accessibility.py app/voice_accessibility_http.py
git commit -m "test: add Voice 1.1A adversarial evidence gates"
```

---

### Task 7: OAuth Contract And Production Acceptance Runbook

**Files:**
- Modify: `chatgpt-gpt-action.yaml`
- Modify: `README.md`
- Create: `docs/voice-1-1a-production-acceptance.md`
- Modify: `tests/test_user_identity_security.py`
- Modify: `tests/test_voice_1_1a_tools.py`

**Interfaces:**
- Consumes: implemented route and configuration names.
- Produces: documented `sara.voice.accessibility` scope and exact gated certification procedure.

- [ ] **Step 1: Write failing documentation-contract tests**

```python
def test_openapi_documents_voice_accessibility_scope_and_routes():
    schema = Path("chatgpt-gpt-action.yaml").read_text(encoding="utf-8")
    assert "sara.voice.accessibility" in schema
    assert "/v1/accessibility/voice/jobs:" in schema
    assert "/v1/accessibility/voice/preferences:" in schema
    assert "SARA_PIPER_SERVICE_TOKEN" not in schema


def test_runbook_keeps_older_capsules_immutable():
    runbook = Path("docs/voice-1-1a-production-acceptance.md").read_text(encoding="utf-8")
    assert "SARA_VOICE_1_1A_ENABLED" in runbook
    assert "SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED" in runbook
    assert "sara-omega-voice-1-1a-" in runbook
    assert "do not modify" in runbook.lower()
```

- [ ] **Step 2: Run documentation tests and confirm RED**

Run: `pytest -q tests/test_user_identity_security.py tests/test_voice_1_1a_tools.py`

Expected: missing scope, route, or runbook assertions fail.

- [ ] **Step 3: Update the OAuth contract and write the runbook**

Document OAuth bearer authorization with `sara.voice.accessibility`, strict request/response schemas, no-store audio/transcript responses, and all user routes. Do not include credentials, callback secrets, private URLs, or sample tokens.

The runbook must contain exact commands for:

```powershell
pytest -q
python -m compileall -q main.py app sara_unified voice_service tools
git diff --check
git status --short --branch
```

It must also define: immutable baseline digest capture; dual-flag staged rollout; certification-user enrollment and OAuth scope; owner entitlement grant; internal probes before public exposure; cross-tenant, quota, privacy, restart, and real WAV transaction evidence; secret scan; ROAD/SISO/Madhouse checkpoints; rollback by disabling either Voice 1.1A flag.

- [ ] **Step 4: Verify GREEN and schema compatibility**

Run: `pytest -q tests/test_user_identity_security.py tests/test_chatgpt_oauth_action_schema.py tests/test_voice_1_1a_tools.py`

Expected: all selected tests pass.

- [ ] **Step 5: Run checkpoint review and commit**

Run: `git diff --check`

Inspect docs and schema for accidental secrets, promises beyond implemented behavior, and any instruction that edits older evidence.

ROAD: require no blocking dependencies.

```bash
git add chatgpt-gpt-action.yaml README.md docs/voice-1-1a-production-acceptance.md tests/test_user_identity_security.py tests/test_voice_1_1a_tools.py
git commit -m "docs: add Voice 1.1A acceptance runbook"
```

---

### Task 8: Full Verification, Deployment, Live Transaction, And Separate ROAD Capsule

**Files:**
- Create at runtime: `outputs/sara-omega-voice-1-1a-immutable-baselines.json`
- Create at runtime: `outputs/sara-omega-voice-1-1a-entitlement.json`
- Create at runtime: `outputs/sara-omega-voice-1-1a-isolation.json`
- Create at runtime: `outputs/sara-omega-voice-1-1a-limits.json`
- Create at runtime: `outputs/sara-omega-voice-1-1a-privacy.json`
- Create at runtime: `outputs/sara-omega-voice-1-1a-restart.json`
- Create at runtime: `outputs/sara-omega-voice-1-1a-transaction.json`
- Create at runtime: `outputs/sara-omega-voice-1-1a-spoken-response.wav`
- Create at runtime: `outputs/sara-omega-voice-1-1a-acceptance-summary.json`

**Interfaces:**
- Consumes: exact tested commit, existing Railway project/services, certification OAuth account, ROAD/SISO/Madhouse gates.
- Produces: deployed Voice 1.1A and its independent code -> deployment -> entitled live audio provenance chain.

- [ ] **Step 1: Run full local verification on the final implementation tree**

Run in the implementation worktree:

```powershell
pytest -q
python -m compileall -q main.py app sara_unified voice_service tools
```

Expected: full suite exits zero; compile validation exits zero. Stop and investigate any failure.

- [ ] **Step 2: Verify the final implementation tree**

Run in the implementation worktree:

```powershell
git diff --check
git status --short --branch
```

Then scan tracked changes and generated evidence for `Bearer`, `OWNER_TOKEN`, `GPT_ACTION_TOKEN`, `SARA_PIPER_SERVICE_TOKEN`, `client_secret`, private service URLs, raw internal UUIDs, and certification transcript plaintext. Expected: no sensitive value is present.

- [ ] **Step 3: Run final adversarial review and ROAD blocker gate**

Re-read the spec acceptance criteria one by one and map each to a passing test or planned live probe. Review the exact diff from the Voice 1.1A spec commit to `HEAD`, prioritizing authentication confusion, tenant lookup, transaction races, transcript expiry, no-store responses, and owner-route regression.

ROAD: require blocking dependencies `PASS` before push or deployment.

- [ ] **Step 4: Push the exact tested commit and stage deployment with exposure disabled**

Record `git rev-parse HEAD`. Push that exact commit to `main` only after verifying `origin/main` is the expected parent. Deploy the existing `sara-omega` service with:

```text
SARA_SOURCE_COMMIT_SHA=<exact tested commit>
SARA_VOICE_1_1A_ENABLED=false
SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=false
```

Do not redeploy Piper unless its accepted deployment is unhealthy or the exact implementation requires a renderer change; this plan does not require one.

- [ ] **Step 5: Capture immutable baselines and run internal activation probes**

Hash every accepted Voice 1.0 and Voice 1.1 evidence artifact into `sara-omega-voice-1-1a-immutable-baselines.json`. Enable only `SARA_VOICE_1_1A_ENABLED=true`, keep the public flag false, and verify all public Voice 1.1A routes return `404` while owner Voice 1.1 synthesis still succeeds.

Configure the existing OAuth client to include `sara.voice.accessibility`. Create a dedicated certification account and owner-granted entitlement without recording credentials.

- [ ] **Step 6: Run isolation, rate-limit, privacy, and restart acceptance**

With public exposure still false, execute the probes through an internal release-test path or local exact-build instance. Prove:

- wrong scope and revoked entitlement fail;
- two certification tenants cannot access each other's jobs, audio, receipts, transcripts, preferences, or stop actions;
- user and tenant minute/day/character limits reject correctly;
- concurrency leases recover after expiry and failure;
- transcript plaintext is absent when disabled and encrypted/expired when enabled;
- restart preserves entitlement, revocation, preferences, and consumed quota;
- Voice 1.1 owner behavior and Piper model-integrity health remain accepted.

Save only redacted results under the required Voice 1.1A filenames.

- [ ] **Step 7: Obtain pre-exposure acceptance and enable the public flag**

Run ROAD/SISO/Madhouse review for the exact SARA deployment and source commit. Require no blocker and a production acceptance result permitting Voice 1.1A exposure. Then set `SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=true` on the existing SARA service.

- [ ] **Step 8: Perform one real entitled-user spoken transaction**

Use the certification OAuth account to submit at least two sentences, retrieve all segment receipts, fetch one authenticated WAV segment, verify its SHA-256 against the receipt, retrieve the transcript only when explicitly preserved, and confirm another certification tenant receives `404` for the same identifiers.

Save the WAV as `outputs/sara-omega-voice-1-1a-spoken-response.wav` and redacted metadata as `outputs/sara-omega-voice-1-1a-transaction.json`.

- [ ] **Step 9: Build and validate the independent acceptance capsule**

Call `build_voice_1_1a_evidence()` with immutable baseline hashes, exact commit, SARA deployment, accepted Piper deployment, transaction, entitlement, isolation, limits, privacy, restart, and ROAD results. Write `outputs/sara-omega-voice-1-1a-acceptance-summary.json`.

Re-run the sensitive-value scan and compare every older evidence artifact against its pre-release digest. Any mismatch fails certification.

- [ ] **Step 10: Run final ROAD acceptance and report provenance**

Require final ROAD production acceptance `PASS` for the exact deployed commit and deployment. Record the final code commit, SARA deployment, Piper deployment, WAV SHA-256, source-response SHA-256, receipt IDs, and acceptance timestamp in the Voice 1.1A summary only.

Do not edit or append to the Voice 1.0 or Voice 1.1 capsules.
