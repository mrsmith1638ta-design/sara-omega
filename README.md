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
- enterprise Runtime Assurance API with audit receipts, evidence adapters,
  live module truth and fail-closed claim suppression
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

## Module Awareness and TITAN

The supplied module-awareness and SARA-TITAN builds are integrated into SARA Omega as
internal modules. See `docs/MODULE_AWARENESS_TITAN_INTEGRATION.md` for endpoint coverage,
attack-vector coverage and the production boundary.
