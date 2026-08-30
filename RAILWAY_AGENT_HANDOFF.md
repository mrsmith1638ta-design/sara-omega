# SARA-OMEGA V3.2.1 — Railway Agent Production Handoff

This handoff is for a Railway-hosted Agent/dev.new session that already has an authenticated Railway CLI. **Do not run `railway login` and do not start a device-code/OAuth flow.**

## Objective

Deploy the canonical `main` branch of `https://github.com/mrsmith1638ta-design/sara-omega` as **SARA-OMEGA V3.2.1**, provision its persistent fail-safe storage and protected runtime variables, prove persistence across a restart, and return the verified public HTTPS URL.

## Security rules

- Never print, echo, commit, upload, or expose `OWNER_TOKEN`.
- Never print, echo, commit, upload, or expose `SARA_FAILSAFE_MASTER_KEY_HEX` / `SARA_FAILSAFE_MASTER_KEY_B64`.
- Never weaken `SARA_FAILSAFE_REQUIRED=true`.
- Never set `SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT=false` to make acceptance pass.
- Never use an insecure production override.
- Keep attack handling fail-closed; do not implement attack-back or retaliation.
- Do not claim production PASS until the live acceptance controller passes after a restart.

## Execute

1. In a clean directory, clone the canonical source and enter it:

   ```bash
   git clone --depth=1 https://github.com/mrsmith1638ta-design/sara-omega.git
   cd sara-omega
   ```

2. Confirm release identity and sanitize the deployment inputs:

   ```bash
   test "$(cat VERSION)" = "3.2.1"
   python3 -m py_compile main.py sara_v32_hardening.py sara_production_bootstrap.py tools/*.py
   bash -n tools/*.sh
   python3 tools/adversarial_gate.py
   docker build -t sara-omega:v3.2.1 .
   ```

3. Confirm the Railway CLI is already authenticated:

   ```bash
   railway whoami
   ```

   If this fails, stop and report `RAILWAY_HOSTED_AGENT_AUTH_UNAVAILABLE`. Do **not** invoke browserless/device authorization.

4. Install the acceptance dependency and run the canonical zero-to-production controller:

   ```bash
   python3 -m pip install --quiet httpx
   bash tools/railway_account_provision.sh
   ```

   The controller is responsible for:
   - creating/reusing project `SARA-OMEGA-V3.2.1`;
   - creating/reusing service `sara-omega`;
   - generating missing protected authority/fail-safe secrets without printing them;
   - setting the production fail-safe variables;
   - attaching persistent storage at `/data`;
   - deploying the checked-out source;
   - creating/resolving a public Railway domain;
   - observing first-boot acceptance evidence;
   - restarting once to prove persistence;
   - running `tools/railway_runtime_acceptance.py` against the live HTTPS service.

5. If the controller fails because a Railway v5.45.x CLI subcommand or JSON shape has changed, inspect the concrete CLI error, patch only the minimum compatibility issue in the working copy, syntax-check the patch, and resume. Do not bypass any SARA production predicate.

## Required completion evidence

Before reporting success, require all of the following:

- Railway deployment state is successful.
- Public URL uses HTTPS.
- `GET /` responds successfully and reports release `3.2.1`.
- `GET /health/live` succeeds.
- `GET /health/ready` succeeds.
- `GET /health/production-acceptance` reports `production_accepted: true`.
- Persistence status is `PROVEN` after the restart.
- Retained fail-safe chain is valid.
- `railway-activation-report.json` exists and records a passing live acceptance run.
- `railway-public-url.txt` contains the final public URL.

## Final response

Return only a concise production summary containing:

- `SARA-OMEGA V3.2.1: PRODUCTION PASS` or the exact blocking predicate;
- the verified public HTTPS URL if PASS;
- project name and service name;
- persistence status;
- acceptance status.

Never include protected token/key values in the response.
