# ROAD MCP — SARA OMEGA CHAT GPT custom

ROAD is a headless [Model Context Protocol](https://modelcontextprotocol.io) server
that provides read-only roadmap, gate-evidence, and certification tools for SARA
OMEGA. ROAD never renders UI, and it never converts inference, user assertion,
model confidence, or missing/inaccessible evidence into `PASS`. Its status
vocabulary is exactly `PASS`, `PARTIAL`, `BLOCKED`, `UNVERIFIED`, `NOT_APPLICABLE`.

## Provenance — READ THIS FIRST

**This source tree is a faithful reconstruction, not a byte-identical snapshot
of the previously deployed service.**

The ROAD MCP service has been running in production on Railway (project
`495f4e9d-1f63-4511-8a02-a971452e9170`, environment
`a726e05d-da03-4af7-9eee-657e17e36770`, service
`9d5b1dc9-aa3a-433d-b31e-7f9d77957b12`, public endpoint
`https://sara-omega-road-mcp-production.up.railway.app/mcp`) since before this
repository tracked it. That deployment was a local Railway build artifact that
was **never committed to any git repository** — there was no prior `road-mcp/`
source tree anywhere in this repo's history to snapshot.

On 2026-09-09, this `road-mcp/` tree was written from scratch by:

1. Reading the design spec
   (`docs/superpowers/specs/2026-09-05-road-test-ci-evidence-design.md`) and
   implementation plan
   (`docs/superpowers/plans/2026-09-05-road-test-ci-evidence.md`), which
   describe ROAD's intended architecture, evidence contract, and file layout.
2. Calling the live deployed server's `tools/list` JSON-RPC method and
   recording the exact tool names, titles, descriptions, input schemas, and
   annotations for all 11 tools (saved verbatim before reconstruction began).
3. Calling each of the 11 live tools (and `initialize`, `resources/list`,
   `prompts/list`) read-only, with representative arguments, to observe exact
   output shapes, field names, status semantics, gate-propagation rules
   (e.g. which gate statuses count as "upstream failures" for downstream
   gates), the roadmap's 34 track titles/summaries/bullets, and the
   evidence-registry/certification/adversarial-suite content — all against
   the public, unauthenticated `/mcp` endpoint.
4. Re-implementing `road-mcp/src/server.ts`, `road-mcp/src/testEvidence.ts`,
   and `road-mcp/data/roadmap.md` to reproduce that observed behavior as
   closely as possible in TypeScript, then diffing this implementation's
   local output against the live server's output tool-by-tool until they
   matched exactly (see verification notes below).

**What was verified to match exactly:** the full `tools/list` response (all 11
tools, byte-for-byte field equality after normalization), `initialize`
capabilities/instructions text, `resources/list`/`prompts/list`
"Method not found" behavior, all 34 roadmap track numbers/titles/summaries/
bullets (including two tracks — 23 and 34 — whose `summary` field is an
authored sentence rather than a join of the first three bullets), the
`get_completion_overview` phase/priority-track structure, and the
`run_certification_check` / `get_blocking_dependencies` / `get_gate_evidence`
gate semantics (including the non-obvious rule that only gates with status
`UNVERIFIED` or `BLOCKED` — not `PARTIAL` — propagate into downstream gates'
`preventedByUpstream` lists and into `get_blocking_dependencies`).

**What cannot be verified and is an open item:** exact byte-for-byte
reconciliation against the previously running instance's actual source files.
This sandbox has only read-only HTTPS access to Railway's GraphQL API
(`https://backboard.railway.app/graphql/v2`), which has no source-download
field, and `railway ssh` requires a raw token value the credential system
deliberately never exposes to agents (HTTPS-proxied credential injection
only; SSH/WebSocket traffic is not intercepted). No mutation or deployment
call was made against Railway at any point in this reconstruction. **Whoever
has direct Railway CLI/SSH access to service `9d5b1dc9-aa3a-433d-b31e-7f9d77957b12`
should diff that container's actual source files against this tree before
treating this as the sole canonical source**, and should specifically check
for any behavior this reconstruction did not have a live tool call to
observe (e.g. rarely-exercised error branches, undocumented environment
variables, or evidence fields not surfaced through any of the 11 tools).

The one deliberate, in-repo, spec-mandated behavioral difference from the
previously observed live server is the `TEST` gate and the new
`test-ci-validation` evidence record (see below) — this is the feature this
change implements, not a reconciliation gap.

## What ROAD does

- Exposes 11 read-only MCP tools over Streamable HTTP at `POST /mcp`
  (stateless, one transport per request — no session persistence):
  `get_completion_overview`, `get_completion_track`,
  `suggest_next_build_phase`, `get_live_runtime_status`,
  `get_production_acceptance`, `get_contextdev_authorization`,
  `get_gate_evidence`, `get_blocking_dependencies`, `run_certification_check`,
  `verify_release_candidate`, `generate_completion_manifest`.
- Loads the canonical 34-track completion roadmap from `data/roadmap.md`.
- Builds a live evidence registry from:
  - `roadmap-source` — the local roadmap file itself;
  - `production-attestation` — SARA's live
    `https://sara-omega-production.up.railway.app/health/production-acceptance`
    endpoint;
  - `contextdev-authorization` — SARA's live
    `https://sara-omega-production.up.railway.app/context-dev/status` endpoint;
  - `test-ci-validation` — **new in this change** (see below).
- Runs `certificationChecks()` over that registry to produce the authoritative
  final gate sequence (`BUILD, TEST, SECURITY, ADVERSARIAL, EPISTEMIC,
  GOVERNANCE, PRIVACY, PERFORMANCE, RECOVERY, MULTI-CLOUD, ACCEPTANCE, SIGN,
  RELEASE`), fail-closed by construction: a gate can only reach `PASS` from
  its own bound evidence, never by inference from another gate, a claimed
  status, or a release version string.

## `test-ci-validation` evidence (this change)

Implements the design in
`docs/superpowers/specs/2026-09-05-road-test-ci-evidence-design.md`. TEST
reaches `PASS` only when **all** of the following hold simultaneously:

1. live SARA production attestation
   (`/health/production-acceptance`) is reachable;
2. it reports a `source_commit_sha` matching `^[0-9a-fA-F]{40}$`;
3. it reports `checkpoint_self_test == true`, `bootstrap_ready == true`, and
   `chain_valid == true`;
4. the canonical GitHub Actions workflow
   (`mrsmith1638ta-design/sara-omega`,
   `.github/workflows/sara-v32-validate.yml`, workflow name
   `SARA-OMEGA V3.2.1 validation`) has exactly one completed, successful run
   whose `head_sha` exactly equals that `source_commit_sha`;
5. that run's `validate` job completed successfully;
6. all six required steps completed successfully: `Compile`,
   `Deployment shell sanitation`, `Native Windows activator syntax`,
   `Production bootstrap tests`, `Focused adversarial gate`,
   `Railway container build`.

Any missing, malformed, mismatched, stale, ambiguous (e.g. two valid
canonical runs for the same SHA), or inaccessible condition yields
`UNVERIFIED`, never `PASS`. See `src/testEvidence.ts` for the implementation
and `tests/test-evidence.test.mjs` for the full positive/negative contract
suite (see "Adversarial requirements" in the design spec).

GitHub evidence is fetched read-only and unauthenticated (public repository
metadata) with a 4.5-second timeout, a 128 KB response-size cap, and
sanitized (query-string/token-stripped) source URLs in output. No GitHub
credential is read, required, or accepted.

## Development

```bash
cd road-mcp
npm ci
npm run check   # tsc --noEmit
npm run build   # tsc -> dist/
npm test        # node --test tests/
npm start       # runs dist/server.js, listens on $PORT (default 3000)
```

## Deployment

`railway.json` configures a Nixpacks build (`npm ci && npm run build`) and
`npm run start` as the start command, matching the existing Railway service's
build/start contract. Deploying this tree to the existing ROAD service was
explicitly out of scope for this change (see the design spec's Task 8) and
was not performed — this reconstruction only canonicalizes source under
version control and adds the TEST/CI evidence feature; it does not deploy.
