# SARA-OMEGA User Continuity and OAuth Enrollment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure single-use enrollment, SARA-owned OAuth accounts, and encrypted user-continuous memory across separate Custom GPT conversations without weakening SARA's existing privilege boundaries.

**Architecture:** Keep all identity state inside the existing FastAPI/Railway deployment. Add a focused `UserIdentityStore` in `app/user_identity.py`, derive domain-separated secrets from the existing memory/fail-safe key, add server-rendered enrollment/OAuth routes in `main.py`, and key personal memory by authenticated internal user UUID rather than chat session alone. Existing owner, GPT Action, tester, source-control, and Railway-control credentials remain separate.

**Tech Stack:** Python 3.11, FastAPI/Starlette, SQLite WAL/FULL, `hashlib.scrypt`, AES-GCM encrypted state, pytest, existing Railway `/data` volume.

**Spec:** `docs/superpowers/specs/2026-09-04-user-continuity-oauth-design.md`

## Global Constraints

- Generic enrollment identifier is exactly `SARA-NEW-USER` by default and grants enrollment only.
- No password, invitation token, authorization code, access token, refresh token, OAuth client secret, or raw enrollment ID may be persisted or logged in plaintext.
- OAuth redirect URIs are exact HTTPS allowlist matches; no wildcard redirect.
- `GPT_ACTION_TOKEN` and `TEST_TOKEN` must not become user identity credentials or access personal-memory operations.
- OAuth user identity must not grant owner, source-control, Railway-control, or admin authority.
- Durable state remains under `SARA_DATA_DIR` on the existing Railway `/data` volume.
- No new cloud project/service/database/volume/domain.
- Existing fail-safe checkpoints remain mandatory before memory mutation.
- TDD: every production behavior below is preceded by a failing test and a CI run proving the failure is for the missing behavior.

---

### Task 1: Identity store, invitation lifecycle, and password verification

**Files:**
- Create: `app/user_identity.py`
- Modify: `app/memory.py`
- Create: `tests/test_user_identity.py`

**Interfaces:**
- Consumes: existing root key material accepted by `app.memory`.
- Produces: `derive_secret_key(context: str, *, required: bool = True) -> bytes | None`, `UserIdentityStore.from_env(required=True)`, `create_invitation()`, `enroll()`, `authenticate_password()`, and immutable account records.

- [ ] **Step 1: Write failing identity tests**

Create tests asserting: root-key domain separation; invitation token absent from raw DB; `SARA-NEW-USER` enrollment succeeds once; mismatch/weak password fails; consumed/expired invite fails; plaintext password absent from DB; valid permanent public user ID authenticates; generic enrollment ID cannot authenticate.

Example assertion shape:

```python
store = UserIdentityStore.from_env(required=True)
invite = store.create_invitation(base_url="https://example.test")
account = store.enroll(
    invite_token=invite.token,
    enrollment_id="SARA-NEW-USER",
    password="Correct-Horse-7!Battery",
    password_confirm="Correct-Horse-7!Battery",
)
assert account.public_user_id.startswith("SARA-U-")
assert store.authenticate_password(account.public_user_id, "Correct-Horse-7!Battery").user_uuid == account.user_uuid
assert b"Correct-Horse-7!Battery" not in (tmp_path / "sara_identity.db").read_bytes()
```

- [ ] **Step 2: Run CI and verify RED**

Open/update the feature PR with tests only. Required failure: import/missing-symbol failures for `app.user_identity` or `derive_secret_key`, not syntax/dependency failures.

- [ ] **Step 3: Implement domain-separated secret derivation**

In `app/memory.py`, expose:

```python
def derive_secret_key(context: str, *, required: bool = True) -> bytes | None:
    material = _decode_key_material()
    if material is None:
        if required:
            raise MemoryKeyError("encrypted_memory_key_not_configured")
        return None
    if not context or len(context) > 128:
        raise MemoryKeyError("invalid_secret_key_context")
    return hashlib.sha256(
        f"SARA-OMEGA:secret:{context}:v1\0".encode("utf-8") + material
    ).digest()
```

Keep existing conversation key derivation behavior compatible by changing `_derive_memory_key` to call `derive_secret_key("encrypted-memory", required=required)` only if the resulting ciphertext compatibility is explicitly preserved; otherwise leave `_derive_memory_key` unchanged and use the new helper only for identity keys.

- [ ] **Step 4: Implement `UserIdentityStore`**

Use SQLite WAL, busy timeout, synchronous FULL, chmod 0600 where supported, `BEGIN IMMEDIATE` for invite consumption/account creation, `secrets.token_urlsafe(32)` for invitation tokens, random UUIDs for internal IDs, 12 random hex characters for `SARA-U-...`, and keyed HMAC-SHA256 hashes for persisted secret/token identifiers.

Password format:

```text
scrypt$v=1$n=32768$r=8$p=1$<salt_b64url>$<digest_b64url>
```

Compute scrypt over `password_utf8 + b"\0" + password_pepper`, where `password_pepper = derive_secret_key("identity-password-pepper")`.

- [ ] **Step 5: Run focused tests GREEN**

Run `pytest -q tests/test_user_identity.py` and require all tests pass.

---

### Task 2: OAuth authorization-code provider and durable brute-force protection

**Files:**
- Modify: `app/user_identity.py`
- Create: `tests/test_user_oauth.py`

**Interfaces:**
- Consumes: `UserIdentityStore` accounts.
- Produces: `OAuthConfiguration`, `OAuthPrincipal`, `validate_authorization_request()`, `issue_authorization_code()`, `exchange_authorization_code()`, `refresh_access_token()`, `resolve_access_token()`, `revoke_token()`, durable authentication lockout methods.

- [ ] **Step 1: Write failing OAuth tests**

Tests must cover exact redirect matching, wrong client secret, code expiry, code single-use, access-token expiry, revocation, refresh rotation, replay rejection, state preservation data, and durable password lockout surviving a new `UserIdentityStore` instance.

- [ ] **Step 2: Run CI and verify RED**

Required failures are missing OAuth interfaces, not unrelated suite failures.

- [ ] **Step 3: Implement OAuth configuration**

Load:

```python
SARA_OAUTH_CLIENT_ID
SARA_OAUTH_CLIENT_SECRET
SARA_OAUTH_REDIRECT_URIS
SARA_OAUTH_SCOPE
SARA_OAUTH_CODE_TTL_SECONDS
SARA_OAUTH_ACCESS_TTL_SECONDS
SARA_OAUTH_REFRESH_TTL_SECONDS
```

Reject configuration if client ID/secret is missing, any redirect URI is non-HTTPS, the list is empty, or a URI contains `*`.

- [ ] **Step 4: Implement opaque OAuth credentials**

Generate codes/tokens with `secrets.token_urlsafe(32)`, persist only keyed hashes, atomically consume codes, rotate refresh tokens, and use constant-time client-secret comparison. Return token material only at creation/exchange time.

- [ ] **Step 5: Implement durable lockout**

Use `auth_failures` keyed by a keyed hash of the public user ID. Default: five failures in a 15-minute window causes a 15-minute lock. Successful authentication clears the failure row. No raw password or public ID is written to failure logs.

- [ ] **Step 6: Run OAuth tests GREEN**

Run `pytest -q tests/test_user_oauth.py tests/test_user_identity.py`.

---

### Task 3: Server-rendered enrollment and OAuth HTTP routes

**Files:**
- Modify: `main.py`
- Create: `tests/test_user_identity_http.py`

**Interfaces:**
- Consumes: `UserIdentityStore` and OAuth interfaces.
- Produces: `/admin/enrollment/invitations`, `/enroll/{token}`, `/oauth/authorize`, `/oauth/token`, `/oauth/revoke`, `/oauth/status`.

- [ ] **Step 1: Write failing HTTP tests**

Use FastAPI `TestClient`. Assert owner-only invite creation; GPT Action/test/user credentials rejected for admin invitation creation; enrollment page contains the three requested fields; mismatched passwords return a safe 400 page; OAuth authorization renders login; successful authorization redirects only to exact configured callback and preserves `state`; token endpoint includes `Cache-Control: no-store` and `Pragma: no-cache`.

- [ ] **Step 2: Run CI and verify RED**

Required failure is 404/missing routes.

- [ ] **Step 3: Implement minimal HTML helpers**

Use `fastapi.responses.HTMLResponse` and `RedirectResponse`; do not add a template engine. Escape all dynamic HTML with `html.escape`. Forms use `autocomplete="new-password"` for enrollment and `autocomplete="current-password"` for OAuth login.

- [ ] **Step 4: Implement invitation/admin and enrollment routes**

`POST /admin/enrollment/invitations` must require `authorize(req) == "owner"`, derive the public base URL from configured `SARA_PUBLIC_BASE_URL` or the request base URL only after host/proxy validation, and return the generic enrollment ID plus one-time URL/expiry.

- [ ] **Step 5: Implement OAuth routes**

Authorization GET/POST validates request before rendering/authentication. Token and revoke endpoints accept standard form data and client credentials from HTTP Basic or form fields, with Basic preferred. Responses never contain secrets except newly issued code/token values required by OAuth.

- [ ] **Step 6: Run HTTP tests GREEN**

Run `pytest -q tests/test_user_identity_http.py tests/test_user_oauth.py tests/test_user_identity.py`.

---

### Task 4: Bind encrypted conversation memory to OAuth user identity

**Files:**
- Modify: `app/memory.py`
- Modify: `main.py`
- Create: `tests/test_user_continuity.py`

**Interfaces:**
- Consumes: OAuth `user_uuid`, optional GPT `session_id`.
- Produces: `ConversationMemory.save_for_user`, `load_for_user`, `load_user_continuity`, `update_user_continuity`, `forget_user`; gateway `AuthContext`; personal memory operations.

- [ ] **Step 1: Write failing continuity/isolation tests**

Test two users with identical session IDs; one user with two session IDs; restart/new store recovery; `memory_recall`; confirmed `memory_forget`; non-OAuth API-key role rejection; no user UUID/session plaintext in raw encrypted DB.

- [ ] **Step 2: Run CI and verify RED**

Required failures are missing user-aware memory APIs and gateway operations.

- [ ] **Step 3: Extend encrypted store safely**

Add encrypted per-user index records so records can be enumerated/deleted without storing raw user UUIDs/session IDs. Record keys remain hashed by `EncryptedStateStore`. A user's index stores its thread IDs only inside AES-GCM ciphertext.

- [ ] **Step 4: Add bounded user continuity**

Store a bounded continuity object with latest thread IDs and recent user/assistant snippets capped by `SARA_MEMORY_CONTINUITY_MAX_ITEMS` (default 50) and existing message-length cleaning. Do not invent facts; continuity is extracted deterministically from stored messages unless a governed summarizer is explicitly added later.

- [ ] **Step 5: Integrate `AuthContext` into `/gpt/action/gateway`**

OAuth bearer token resolution occurs before shared GPT Action token fallback. Add `role="user"` rate limits. Personal memory operations require `auth_kind == "oauth"` and nonempty `user_uuid`. Existing public/status assurance operations remain compatible with owner/action/test credentials.

- [ ] **Step 6: Persist solve continuity**

For OAuth `solve`, attach bounded prior continuity to `Problem.context["sara_user_continuity"]`, never to another user. After successful solve and fail-safe checkpoint, append the user query and bounded verdict representation to the user/thread encrypted store and refresh the continuity index.

- [ ] **Step 7: Run continuity tests GREEN**

Run `pytest -q tests/test_user_continuity.py tests/test_secure_continuity.py`.

---

### Task 5: OpenAPI, runtime status, and adversarial compatibility

**Files:**
- Modify: `chatgpt-gpt-action.yaml`
- Modify: `main.py`
- Modify: `tests/test_privileged_control_plane.py`
- Create: `tests/test_user_identity_security.py`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: documented memory operations and OAuth readiness status without secret leakage.

- [ ] **Step 1: Write failing security/schema tests**

Assert OpenAPI contains `memory_status`, `memory_recall`, `memory_forget`; no client secret or password fields are embedded as fixed values; OAuth user cannot invoke privileged control plane; GPT/test tokens cannot call personal memory; logs sanitize bearer/token/password values; `/oauth/status` exposes booleans/configuration state but no secret values.

- [ ] **Step 2: Run CI and verify RED**

- [ ] **Step 3: Update schema and status**

Add the three operation enum values and document `session_id` as thread identity only. Keep bearer scheme in OpenAPI because ChatGPT injects the OAuth bearer token at runtime; configure OAuth in the GPT editor rather than hardcoding OAuth secrets into OpenAPI.

- [ ] **Step 4: Run focused security tests GREEN**

Run `pytest -q tests/test_user_identity_security.py tests/test_privileged_control_plane.py`.

---

### Task 6: Full verification, exact commit, existing Railway deployment

**Files:**
- No new production behavior; verification/deployment only.

**Interfaces:**
- Consumes: exact tested feature branch tree.
- Produces: production commit/deployment evidence.

- [ ] **Step 1: Full CI validation**

Require feature PR CI success for compile, `pytest -q`, existing adversarial gate, and Docker build.

- [ ] **Step 2: Diff/secret review**

Inspect compare against parent `d6069290d4484f1bb176a37a85dd4fedad0d0c77`. Reject any credential/token/password material, accidental staging files, control-plane weakening, or cloud-resource creation.

- [ ] **Step 3: Create exact production commit**

Advance `main` only to the exact verified feature tree after confirming current `main` is still the expected parent or explicitly reconciling any intervening commits. Do not force-push.

- [ ] **Step 4: Configure non-callback Railway variables without deploying**

Generate strong random values for `SARA_OAUTH_CLIENT_ID` and `SARA_OAUTH_CLIENT_SECRET` only if the existing Railway service does not already have them. Set `SARA_ENROLLMENT_ID=SARA-NEW-USER` and `SARA_PUBLIC_BASE_URL=https://sara-omega-production.up.railway.app`. Do not invent `SARA_OAUTH_REDIRECT_URIS`; leave OAuth status `CONFIGURATION_REQUIRED` until the exact callback URI from the GPT editor is available.

- [ ] **Step 5: Exact-commit deployment with CAS/idempotency**

Use the existing project `d231d279-92f3-435d-a1d6-c38849b6bfc8`, service `c876b916-8089-470f-b655-4c9a8d957f52`, environment `502fe307-8e47-41a7-9a83-525a61929670`. Read current deployment, reserve idempotency before mutation, re-read current deployment for compare-and-swap, submit the exact commit once, and mark uncertain mutation `SUBMISSION_UNVERIFIED` with no retry.

- [ ] **Step 6: Live acceptance**

Require HTTP 200 for `/health/live`, `/health/ready`, `/health/production-acceptance`, and `/oauth/status`. Require production acceptance remains true and persistence remains PROVEN. Create one invitation through owner authentication only if a safe connected credential path is available; otherwise verify invitation creation through tests and report that live invite issuance still requires owner-authenticated use.

- [ ] **Step 7: Final GPT connection statement**

Report backend status separately from Custom GPT OAuth connection status. Do not claim cross-chat identity is live until `SARA_OAUTH_REDIRECT_URIS` contains the exact callback from the GPT editor and a real user completes OAuth successfully.