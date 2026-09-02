# SARA ChatGPT Action Gateway

SARA-OMEGA V3.2.1 exposes one governed Railway Action endpoint for the custom GPT:

```text
POST https://sara-omega-production.up.railway.app/gpt/action/gateway
```

The OpenAPI schema is in `chatgpt-gpt-action.yaml` and is also served by the runtime at:

```text
https://sara-omega-production.up.railway.app/gpt/action/openapi.yaml
```

## GPT Builder Setup

1. Open the custom GPT editor.
2. Add one Action.
3. Import or paste `chatgpt-gpt-action.yaml`.
4. Set authentication to API key / Bearer token.
5. Use the Railway `OWNER_TOKEN` or a dedicated governed token from Railway variables.

Do not paste secrets into normal chat. The GPT Action secret belongs only in the GPT editor authentication field.

## Sync Resolver

When the ChatGPT editor or browser path is unavailable, run the resolver before retrying the editor import:

```powershell
.\.venv\Scripts\python.exe tools\custom_gpt_action_sync_resolver.py
```

The resolver verifies the local OpenAPI contract, the hosted Railway schema, local Git object database integrity, and the latest GitHub validation run. A passing resolver means the backend and schema are ready; only the manual GPT editor import remains.

## Supported Gateway Operations

- `status`: live Railway runtime, production acceptance summary, assurance domains, module awareness, TITAN health.
- `production_acceptance`: sanitized V3.2.1 acceptance evidence.
- `module_awareness`: module registry awareness, count, and diff.
- `runtime_assurance`: active evidence-domain routing state.
- `concentration`: objective-lock scoring to detect deviation from the user's requested problem.
- `hawkins_chaos`: nonlinear perturbation and trajectory-stability analysis.
- `titan_health`: TITAN integrated subsystem status.
- `verify_output`: fail-closed claim verification before ChatGPT repeats generated text.
- `solve`: routes a user request through SARA governance, authority, module routing, evidence verification, and audit ledger.

## Runtime Contract

The gateway reuses the existing Railway token authorization, rate limits, fail-safe readiness, checkpointing, and audit trail. Mutating or trust-sensitive operations fail closed if the V3.2.1 fail-safe is unavailable.

The concentration governor sits before final rendering as an objective-lock layer. It returns `refocus_before_final` when the answer drifts from the user's requested code/programming/problem-solving objective.

Hawkins Chaos is integrated as an advisory mathematical layer between awareness/truth and TITAN decision context. It can downgrade effective confidence when reasoning trajectories are unstable, but it cannot override truth, authorization, runtime assurance, or fail-safe controls.
