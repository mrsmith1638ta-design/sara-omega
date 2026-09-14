# SARA Public + ATS Azure Cross-Reference

## Runtime Boundary

`sara_public.py` is a separate SARA Public + ATS commercial runtime. It is not the existing SARA-OMEGA V3.2.1 production runtime and does not inherit SARA-OMEGA Railway production acceptance, ROAD PASS, or live acceptance evidence.

Its production acceptance state remains `UNVERIFIED` until this exact build is independently tested, ROAD-certified, deployed, and accepted.

## Cross-Reference

| Area | Existing repository state | SARA Public + ATS state |
| --- | --- | --- |
| Web runtime | Existing FastAPI apps in `main.py`, `sara_web.py`, tutor modules, and app routers | New isolated FastAPI app in `sara_public.py` |
| Governance language | SIOS, ROAD, MADHOUSE, epistemic boundaries | Reuses the same vocabulary but starts with no inherited PASS |
| ATS support | `app/ats_intelligence.py` and related tests provide governed ATS intelligence | Adds commercial ATS analysis endpoints and resume-specific processing |
| Billing | No Stripe runtime in the existing production app | Adds Stripe checkout and webhook handling |
| Auth | Existing user/OAuth gateway modules | Adds OIDC/JWKS bearer-token validation |
| Persistence | Existing SQLite/WAL patterns and Railway `/data` persistence evidence | Uses single-worker SQLite MVP; must migrate before horizontal commercial scaling |
| Deployment | Railway-oriented deployment files remain unchanged | Azure-targeted packaging is isolated in `Dockerfile.sara-public` and `requirements-sara-public.txt` |

## Azure Configuration Names

Set secrets and environment-specific values in Azure App Settings, never in GitHub or chat:

- `APP_ENV`
- `SARA_DB_PATH`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `SARA_MODEL_FREE`
- `SARA_MODEL_CORE`
- `SARA_MODEL_PRO`
- `SARA_MODEL_ELITE`
- `OIDC_ISSUER`
- `OIDC_AUDIENCE`
- `OIDC_JWKS_URL`
- `OIDC_ALGORITHMS`
- `ROAD_VERIFY_URL`
- `ROAD_TOKEN`
- `SARA_BUILD_SHA`
- `SARA_POLICY_VERSION`
- `RESUME_AES_KEY_B64`
- `RESUME_HMAC_KEY_B64`
- `RESUME_SCHEMA_VERSION`
- `RESUME_TTL_DAYS`
- `RESUME_MAX_BYTES`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `CHECKOUT_SUCCESS_URL`
- `CHECKOUT_CANCEL_URL`
- `STRIPE_PRICE_SARA_CORE`
- `STRIPE_PRICE_SARA_PRO`
- `STRIPE_PRICE_SARA_ELITE`
- `STRIPE_PRICE_ATS_90D`
- `STRIPE_PRICE_ATS_MONTHLY`

## Deployment Verification

Minimum local gates before Azure promotion:

1. `python -m py_compile sara_public.py`
2. `python sara_public.py --self-test`
3. `python -m pytest -q tests/test_sara_public_azure_packaging.py`
4. Container or Azure build succeeds for the exact source tree.
5. Azure `/health` returns the runtime health object with `production_acceptance` still `UNVERIFIED`.

Do not claim production acceptance from Azure health alone. ROAD must verify and accept the exact deployed build before the acceptance state can change.
