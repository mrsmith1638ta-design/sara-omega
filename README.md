# SARA-OMEGA Full Architecture v1.0

A runnable reference implementation of the governed decision-intelligence architecture developed
for SARA-OMEGA.

## What is implemented

- SARA Core architectural invariants
- OMEGA Protocol documentation
- deterministic Governance Core
- Authority Engine
- Problem Engine
- integrated module awareness, route harmonization, temporal context, drift detection
  and continuity memory from the module-awareness build
- integrated SARA-TITAN signed VOICE chain, bus, deployment gate and apex authority
- OMEGA Router
- OMEGA Council specialist dispatch
- triangle expansion data analytics specialist for metrics, telemetry and dataset review
- Perplexity Sonar research connector
- Codex local CLI connector
- Cursor local CLI connector
- conservative claim/evidence verification states
- OpenAI Responses API semantic synthesis judge
- OMEGA Verdict schema
- SQLite Decision Ledger
- outcome + lesson recording
- prior-decision context supplied to semantic synthesis
- FastAPI service
- governed Piper voice synthesis with an isolated internal renderer and fixed SARA voice profile
- enterprise Runtime Assurance API with audit receipts, evidence adapters,
  live module truth and fail-closed claim suppression
- Madhouse Agent adversarial code critique gate with syntax, logic, security,
  duplication, recurring-failure fingerprinting and evidence-led BLOCK decisions
- Cursor/agent repository rules
- offline unit tests
- preserved original SARA documentation

## Important boundary

This is a full *code architecture*, not a claim that every future capability is already solved.
Outcome learning is currently retrieval/context learning, not autonomous model-weight training.
Evidence verification is conservative provenance/corroboration classification; it does not magically
prove a source true. Human authorization is enforced at the service logic level and should be connected
to enterprise identity/RBAC before production use.

## Run

1. Create a Python 3.11+ virtual environment.
2. Install: `pip install -e .`
3. Copy `.env.example` to `.env`.
4. Add only the credentials/providers you intend to use.
5. Start: `uvicorn app.server:app --reload`
6. Open `/docs` for the generated API interface.

For offline tests: `pip install -e '.[dev]'` then `pytest`.

## One-Command Build

On Windows, run:

```powershell
.\build.cmd
```

The build script creates or reuses `.venv`, installs the package with test dependencies,
compiles `app` and `tests`, runs the offline test suite, refreshes `BUILD_VERIFICATION.md`,
regenerates `MANIFEST.sha256`, verifies the manifest, and writes a clean ZIP artifact to
`dist`.

## Railway Production Consume

To make an existing Railway production codebase consume this verified build without replacing
its bootstrap, run a dry-run first:

```powershell
.\railway-consume.cmd -TargetPath "C:\path\to\railway-production"
```

Then apply only after the plan names the correct target:

```powershell
.\railway-consume.cmd -TargetPath "C:\path\to\railway-production" -Apply
```

The consume script verifies this source build, creates a full timestamped backup of the target,
copies the verified enterprise runtime files, preserves `.env`, `/data`, `config`, Railway
boot files, requirements, and existing V3/server/bootstrap files, then mounts the enterprise
runtime router into the target FastAPI app with one guarded include.

## Local agent safety

Codex/Cursor subprocess execution is OFF by default. Review their permissions and set
`SARA_ALLOW_LOCAL_AGENTS=true` only in an environment where you intend SARA to invoke them.
Cursor is invoked in Ask mode by default. High-impact execution belongs behind a separate approved
executor, not inside the reasoning path.

## API example

POST `/solve`

    {
      "query": "Research the latest requirements and assess our repository implementation",
      "objective": "Determine whether the implementation meets current requirements",
      "council": true,
      "authority_level": 1
    }

The returned object is an OMEGA Verdict with governance disposition, claims, evidence state,
providers used and a decision_id for later outcome recording.

## Runtime Assurance

For regulated AI output, call `POST /runtime-assurance/verify-output` before rendering
generated text. The gate checks deployment-state, financial, medical, legal and
data analytics claims against configured evidence adapters or supplied live module truth. Unsupported,
unavailable or contradicted checkable claims return `BLOCK` with `action: suppress`
and a signed audit receipt.

Set `SARA_RUNTIME_ASSURANCE_SECRET` before using the runtime assurance endpoints.
The service fails closed if it cannot issue or verify receipts.

## Madhouse Agent

Madhouse is SARA's controlled divergence and hostile code-quality gate. It reviews generated
code as an untrusted candidate, emits findings, records evidence-led failure fingerprints, and
returns either `BLOCKED` or `READY_FOR_VERIFICATION`.

Madhouse can block a candidate. It cannot grant PASS, deploy, certify production readiness,
override SIOS, override ROAD, or promote its own hypothesis to verified truth.

Its evidence ledger distinguishes reproduced failures from deterministic heuristics. Parser/compiler
failures and recurring failure families can be `VERIFIED`; static code, security-pattern, quality and
duplication signals remain `SUPPORTED` until independent runtime, test or exploit evidence confirms
them. Recurrence uses both exact fingerprints and normalized failure-family fingerprints so cosmetic
renames do not hide repeated repair failures.

Run the API locally:

```powershell
uvicorn main:app --reload
```

Review a code candidate:

```powershell
curl -X POST http://127.0.0.1:8000/madhouse/review `
  -H "Content-Type: application/json" `
  -d "{\"candidate_id\":\"build-047\",\"language\":\"python\",\"generated_code\":\"def broken(:`n    return True`n\"}"
```

The ChatGPT action gateway also exposes `operation: "madhouse_review"` with the candidate fields
inside `context`: `candidate_id`, `language`, `generated_code`, `requirements`, and
`previous_failures`.

## Module Awareness and TITAN

The supplied module-awareness and SARA-TITAN builds are integrated into SARA Omega as
internal modules. See `docs/MODULE_AWARENESS_TITAN_INTEGRATION.md` for endpoint coverage,
attack-vector coverage and the production boundary.

## SARA Piper Voice Synthesis

SARA Unified exposes a governed voice capability using the fixed profile
`sara_elegant_british_v1`, backed by Piper `en_GB-cori-high`. The product voice direction is a
British English female presentation with an elegant, calm, articulate professional register.

Voice is disabled by default. SARA core does not install or import the Piper runtime. Instead,
`POST /v1/voice/synthesize` sends authorized, bounded text to the separately deployed internal
service under `voice_service/`, and returns WAV audio. `GET /v1/voice/profile` exposes the
non-sensitive profile metadata.

Enable the core route only after provisioning the private Piper service:

```text
SARA_VOICE_ENABLED=true
SARA_PIPER_SERVICE_URL=http://<private-piper-service>:5000
SARA_PIPER_SERVICE_TOKEN=<shared-random-service-token>
SARA_VOICE_TIMEOUT_SECONDS=15
SARA_VOICE_MAX_CHARACTERS=4000
```

The Piper service separately requires:

```text
PIPER_MODEL_PATH=/models/en_GB-cori-high.onnx
SARA_VOICE_SERVICE_TOKEN=<same-shared-random-service-token>
```

The main SARA audit ledger records only the voice profile ID, character count, and SHA-256 digest
of synthesized text for this endpoint; it does not store the raw spoken text in the synthesis event.
See `voice_service/README.md` for model provisioning, container deployment, and licensing-boundary
notes.

### Voice 1.1 hardening

Voice 1.1 is an owner/internal-only certification surface. Enable it only with
`SARA_VOICE_1_1_ENABLED=true` after the Voice 1.1 implementation has passed repository tests and
production acceptance. Public accessibility voice routes remain disabled until a separate Voice 1.1A
release gate.

### Voice 1.1A accessibility API

Voice 1.1A is a separately certified, limited user-facing accessibility surface. It reuses the
accepted Voice 1.1 engine but adds OAuth scope `sara.voice.accessibility`, durable owner-granted
entitlements, server-resolved individual tenants, persistent user and tenant quotas, encrypted
bounded transcript retention, and authenticated no-store WAV delivery.

It is disabled unless both release gates are true:

```text
SARA_VOICE_1_1A_ENABLED=true
SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED=true
```

The OAuth client must allow `sara.voice.accessibility`, and the owner must grant the enrolled user a
Voice 1.1A entitlement before any user route succeeds. Caller-supplied tenant, model, voice,
pronunciation, service, and raw Piper control fields are rejected. Disabling either release gate
returns the entire user-facing surface to `404` without disabling owner-only Voice 1.1.

See `docs/voice-1-1a-production-acceptance.md` for the staged certification and rollback procedure.
