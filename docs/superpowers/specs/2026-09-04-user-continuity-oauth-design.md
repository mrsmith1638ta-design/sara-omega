# SARA-OMEGA User Continuity and OAuth Enrollment Design

## Objective

Give every SARA user a durable identity that survives separate Custom GPT conversations while preserving SARA-OMEGA's existing fail-closed security, encrypted SQLite continuity, owner/test/action separation, and Railway `/data` persistence.

The public onboarding experience is:

1. The owner generates a single-use invitation link.
2. The owner sends the link together with the generic enrollment ID `SARA-NEW-USER`.
3. The user opens the link and enters the enrollment ID, a new password, and the same password again.
4. SARA atomically consumes the invitation and creates a unique permanent account.
5. SARA displays a permanent human-readable user ID such as `SARA-U-<12 hex characters>`.
6. The user connects the SARA Custom GPT through OAuth.
7. Future GPT Action calls carry a SARA OAuth access token. SARA resolves that token to the same internal user UUID across different chat/session IDs.
8. Conversation memory is indexed by the authenticated user identity plus conversation thread, with a durable user-level continuity summary/history available across threads.

## Non-negotiable security boundaries

- `SARA-NEW-USER` is an enrollment identifier only. It is never a permanent username, authentication credential, role, or execution authority.
- Every invitation is cryptographically random, single-use, expiration-bound, stored only as a keyed hash, and consumed in the same SQLite transaction that creates the account.
- Passwords are never stored or logged in plaintext. Password verification uses `hashlib.scrypt` with a unique random salt and a domain-separated server-side pepper derived from SARA's existing memory/fail-safe key material.
- The user-facing permanent ID is not the database primary key. Accounts use a random internal UUID.
- OAuth authorization codes and access/refresh tokens are random opaque values; only keyed hashes are persisted.
- Authorization codes are one-time and short-lived. Access tokens are short-lived. Refresh tokens are revocable and rotated on successful refresh.
- OAuth client validation is hard-bound to configured SARA client ID, client secret, and exact allowed redirect URI(s). No wildcard redirects.
- OAuth supports `state` pass-through and exact redirect validation. `response_type` must be `code`.
- Login and enrollment endpoints are rate-limited with durable failure counters/lock windows so restarts do not reset brute-force protection.
- Unknown, expired, revoked, malformed, or conflicting identity fails closed. SARA never guesses a user from IP address, session ID, GPT Action token, or display name.
- `GPT_ACTION_TOKEN` and `TEST_TOKEN` cannot become user OAuth credentials and cannot access another user's memory.
- Existing owner privilege remains separate from user identity. Authenticating as a user grants no source-control, Railway-control, owner, or admin authority.
- Privileged control plane code in `app/control_plane.py` remains unreachable through OAuth user tokens.
- Secrets and passwords must be redacted from logs. User IDs may be logged only in bounded public-ID form, not with raw tokens.
- No new cloud project/service/database/volume/domain is created. All durable state stays on the existing Railway `/data` volume.

## Cryptographic keying

Expose a public helper in `app/memory.py`:

```python
def derive_secret_key(context: str, *, required: bool = True) -> bytes | None:
    ...
```

It derives a 32-byte key from the same accepted memory/fail-safe root key material using SHA-256 domain separation:

`SARA-OMEGA:secret:<context>:v1\0 || root_key_material`

Existing encrypted conversation storage continues to use its own domain-separated key. Identity hashing/pepper contexts are distinct.

## Identity persistence

Create `app/user_identity.py` with `UserIdentityStore` backed by `SARA_DATA_DIR/sara_identity.db` using SQLite WAL, `busy_timeout=10000`, and `synchronous=FULL`.

Tables:

### `users`
- `user_uuid TEXT PRIMARY KEY`
- `public_user_id TEXT UNIQUE NOT NULL`
- `password_hash TEXT NOT NULL`
- `status TEXT NOT NULL` (`ACTIVE`, `DISABLED`)
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### `enrollment_invites`
- `token_hash TEXT PRIMARY KEY`
- `enrollment_id_hash TEXT NOT NULL`
- `expires_at TEXT NOT NULL`
- `consumed_at TEXT`
- `user_uuid TEXT`
- `created_at TEXT NOT NULL`

### `oauth_codes`
- `code_hash TEXT PRIMARY KEY`
- `user_uuid TEXT NOT NULL`
- `client_id_hash TEXT NOT NULL`
- `redirect_uri_hash TEXT NOT NULL`
- `scope TEXT NOT NULL`
- `expires_at TEXT NOT NULL`
- `consumed_at TEXT`
- `created_at TEXT NOT NULL`

### `oauth_tokens`
- `token_hash TEXT PRIMARY KEY`
- `token_type TEXT NOT NULL` (`ACCESS`, `REFRESH`)
- `user_uuid TEXT NOT NULL`
- `client_id_hash TEXT NOT NULL`
- `scope TEXT NOT NULL`
- `expires_at TEXT NOT NULL`
- `revoked_at TEXT`
- `parent_hash TEXT`
- `created_at TEXT NOT NULL`

### `auth_failures`
- `subject_hash TEXT PRIMARY KEY`
- `failure_count INTEGER NOT NULL`
- `window_started_at TEXT NOT NULL`
- `locked_until TEXT`
- `updated_at TEXT NOT NULL`

Raw invitation tokens, passwords, OAuth codes, access tokens, refresh tokens, client secrets, and raw enrollment IDs are never persisted.

## Enrollment

Configuration:

- `SARA_ENROLLMENT_ID` defaults to `SARA-NEW-USER`.
- `SARA_INVITE_TTL_SECONDS` defaults to `86400`.
- `SARA_GPT_URL` is optional and is only used for a post-enrollment link.

Owner-only endpoint:

`POST /admin/enrollment/invitations`

Authentication: existing `OWNER_TOKEN` only. `GPT_ACTION_TOKEN`, `TEST_TOKEN`, and OAuth user tokens receive 403.

Response contains:

```json
{
  "enrollment_id": "SARA-NEW-USER",
  "enrollment_url": "https://sara-omega-production.up.railway.app/enroll/<random-token>",
  "expires_at": "..."
}
```

GET `/enroll/{token}` renders a minimal server-side HTML form with fields:

- Enrollment ID
- Create Password
- Confirm Password

POST `/enroll/{token}` validates:

- invitation exists, is unused, and not expired;
- enrollment ID matches configured value using constant-time comparison after keyed hashing;
- password and confirmation match;
- password is 12-128 characters and contains at least three of uppercase, lowercase, digit, and symbol classes;
- current invitation/subject is not rate-limit locked.

On success, one `BEGIN IMMEDIATE` transaction creates the user and marks the invitation consumed. The same invitation cannot create a second account even under concurrent requests.

## OAuth provider

Configuration:

- `SARA_OAUTH_CLIENT_ID` required to enable OAuth.
- `SARA_OAUTH_CLIENT_SECRET` required to enable OAuth.
- `SARA_OAUTH_REDIRECT_URIS` required, comma-separated exact HTTPS callback URI(s) copied from the Custom GPT editor.
- `SARA_OAUTH_ACCESS_TTL_SECONDS` default `3600`.
- `SARA_OAUTH_REFRESH_TTL_SECONDS` default `2592000`.
- `SARA_OAUTH_CODE_TTL_SECONDS` default `300`.
- `SARA_OAUTH_SCOPE` default `sara.memory sara.solve`.

Endpoints:

- `GET /oauth/authorize`
- `POST /oauth/authorize`
- `POST /oauth/token`
- `POST /oauth/revoke`
- `GET /oauth/status`

`GET /oauth/authorize` validates client ID, exact redirect URI, response type, and requested scope before rendering the login form. Hidden fields preserve `client_id`, `redirect_uri`, `state`, `scope`, and `response_type`.

`POST /oauth/authorize` authenticates `public_user_id` + password. It never accepts `SARA-NEW-USER` as a login identity. Successful authentication creates a one-time authorization code and redirects to the exact validated callback with `code` and the unchanged `state`.

`POST /oauth/token` supports:

- `grant_type=authorization_code`: validates client credentials, exact redirect URI, unused/unexpired code, atomically consumes the code, and returns access + refresh tokens.
- `grant_type=refresh_token`: validates client credentials and active refresh token, rotates the refresh token, revokes the old refresh token, and returns a fresh access + refresh pair.

`POST /oauth/revoke` revokes a supplied token when the client credentials are valid.

No token endpoint response is cached. OAuth responses use `Cache-Control: no-store` and `Pragma: no-cache`.

## Auth integration with existing GPT Action gateway

Add an immutable `AuthContext` containing:

- `role`: `owner`, `action`, `tester`, or `user`
- `user_uuid`: populated only for OAuth users
- `public_user_id`: populated only for OAuth users
- `auth_kind`: `owner_token`, `gpt_action_token`, `test_token`, or `oauth`

Existing `authorize(req)` remains compatible for non-user endpoints, but `/gpt/action/gateway` resolves the full `AuthContext`.

For OAuth users:

- rate-limit key is based on the internal user UUID, never IP/session;
- `solve`, `verify_output`, and memory operations use user authority level 1;
- user identity does not elevate execution authority.

The existing shared `GPT_ACTION_TOKEN` may continue to call non-personal status/assurance operations for compatibility, but personal memory operations require OAuth identity.

## Cross-chat memory model

Extend `ConversationMemory` with user-aware record keys:

```python
def conversation_key(user_uuid: str, session_id: str) -> str:
    ...

def user_continuity_key(user_uuid: str) -> str:
    ...
```

Add methods:

```python
save_for_user(user_uuid: str, session_id: str, messages: list[dict[str, str]]) -> None
load_for_user(user_uuid: str, session_id: str) -> list[dict[str, str]]
list_user_threads(user_uuid: str, limit: int = 20) -> list[dict[str, Any]]
load_user_continuity(user_uuid: str) -> dict[str, Any]
update_user_continuity(user_uuid: str, *, session_id: str, messages: list[dict[str, str]]) -> dict[str, Any]
forget_user(user_uuid: str) -> None
```

`EncryptedStateStore` receives safe delete/list-by-scope support using hashed metadata that does not expose raw user UUIDs/session IDs in the SQLite file.

For each OAuth `solve` request:

1. Require authenticated `user_uuid`.
2. Use supplied `session_id` when present; otherwise generate an isolated thread ID for that request only and return it.
3. Load that user/thread's durable transcript.
4. Load the user's durable continuity object containing bounded recent-thread summaries and explicitly remembered facts.
5. Inject only bounded continuity into the problem context; never another user's memory.
6. Run SARA governance/solve.
7. Persist the user/thread transcript and updated continuity only after fail-safe pre-mutation succeeds.

The continuity object is bounded and contains no secrets/tokens. It records recent user/assistant content summaries/facts needed for future SARA conversations, not unlimited raw context injection.

## User memory controls

Add GPT Action operations:

- `memory_status`: returns the authenticated public SARA user ID and counts/metadata only.
- `memory_recall`: returns a bounded continuity summary for the authenticated user.
- `memory_forget`: deletes all encrypted conversation and continuity records for the authenticated user after explicit `context.confirm=true`; account credentials remain active.

All three require OAuth. Shared API-key roles receive 401/403 for these operations.

## OpenAPI and Custom GPT configuration

Update `chatgpt-gpt-action.yaml` to document OAuth bearer semantics and the three memory operations. The OpenAPI file does not contain the OAuth client secret.

The Custom GPT editor must be switched from API-key authentication to OAuth using:

- Authorization URL: `https://sara-omega-production.up.railway.app/oauth/authorize`
- Token URL: `https://sara-omega-production.up.railway.app/oauth/token`
- Client ID: value of `SARA_OAUTH_CLIENT_ID`
- Client Secret: value of `SARA_OAUTH_CLIENT_SECRET`
- Scope: `sara.memory sara.solve`
- Callback URI: exact URI supplied by the GPT editor, then added to `SARA_OAUTH_REDIRECT_URIS`

The backend must report OAuth as not ready until all required values including the callback URI are configured. It must never accept wildcard callback URIs.

## Tests

Add adversarial tests covering:

- invitation token not persisted plaintext;
- generic enrollment ID cannot log in;
- password mismatch rejected;
- weak password rejected;
- invitation expires;
- invitation consumed exactly once;
- two concurrent enrollment attempts cannot create two accounts from one invite;
- password plaintext absent from DB;
- wrong password and brute-force lockout;
- two users cannot read each other's memory;
- same user with two different session IDs retains user continuity;
- same session ID under different users remains isolated;
- continuity survives new store instances/restart;
- OAuth exact redirect URI validation;
- authorization code single-use and expiry;
- invalid client secret rejected;
- access token expiry/revocation;
- refresh token rotation and replay rejection;
- OAuth user cannot become owner/control-plane authority;
- `GPT_ACTION_TOKEN`/`TEST_TOKEN` cannot access personal memory operations;
- forget deletes only the authenticated user's memory;
- no raw passwords/invite tokens/OAuth tokens appear in logs or SQLite bytes;
- existing 93-test security/continuity suite remains green.

## Deployment acceptance

Before production mutation:

- run full `pytest -q`;
- run compile validation and existing adversarial gate;
- build Docker image;
- inspect diff for secrets;
- verify `main` remains the expected production parent before merge;
- merge/push only the tested exact tree;
- deploy exactly the resulting commit to the existing Railway project/service/environment with the existing compare-and-swap/idempotency discipline;
- do not create cloud resources;
- verify `/health/live`, `/health/ready`, `/health/production-acceptance`, `/oauth/status`, and an enrollment/OAuth smoke test without exposing credentials.

OAuth may be `CONFIGURATION_REQUIRED` until the Custom GPT editor callback URI is known and copied into Railway. That state is not represented as fully connected cross-chat identity until the callback is configured and a real OAuth login succeeds.