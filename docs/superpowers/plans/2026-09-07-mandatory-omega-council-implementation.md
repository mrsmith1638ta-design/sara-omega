# Mandatory OMEGA Council Implementation Plan

> **Execution requirement:** implement this plan with test-driven development and verification-before-completion. Do not deploy, push to production, or weaken governance to make tests pass.

**Goal:** Make every SARA-OMEGA request traverse the mandatory OMEGA Council lifecycle while selectively invoking only relevant specialists, preserving the reasoning/execution authority boundary, and recording every durable finalized verdict in an append-only hash-chained ledger that requires verified Ed25519 and ML-DSA signatures over the same canonical digest.

**Architecture:** Refactor `SaraOmega.solve()` into an explicit staged Council coordinator. Keep specialist routing relevance-based. Add deterministic cross-examination and stress-test records, a dedicated append-only verdict ledger, and an external signer abstraction that never accepts raw private keys. The application may surface an explicitly non-durable reasoning result when the signing/durability gate is unavailable, but it must never call that result a durable OMEGA verdict. The gateway exposes Council and integrity metadata without adding execution privileges.

**Tech stack:** Python 3.11+, FastAPI 0.115.x, Pydantic 2.x, SQLite WAL/FULL durability, `cryptography` for public-key Ed25519 verification primitives where needed, HTTPX for external signer calls, pytest.

**Design spec:** `docs/superpowers/specs/2026-09-07-omega-council-default-design.md`

## Invariants

- Mandatory internal lifecycle: `OBSERVE -> MAP -> EVALUATE -> GENERATE -> CROSS_EXAMINE -> STRESS_TEST -> SYNTHESIZE -> GOVERN -> VERDICT -> RECORD`.
- `Problem.council=False` cannot bypass the lifecycle.
- External providers are invoked only when relevant; `council=True` no longer means blanket fan-out.
- Provider output remains claims/evidence, never truth by consensus.
- Council is advisory. No Council method may deploy, send, purchase, mutate repositories, change cloud state, or perform another external mutation.
- Governance may suppress external specialist calls before they occur, but suppressed stages still appear in the Council trace.
- Durable verdict acceptance requires canonicalization, valid prior chain, Ed25519 signature+verification, ML-DSA signature+verification, SQLite commit, read-after-write confirmation, and chain-head confirmation.
- Ed25519 and ML-DSA sign exactly the same canonical record digest.
- No raw signing private key is accepted from environment variables, repository files, local application storage, verdict payloads, or logs.
- No silent downgrade from ML-DSA.
- Corrections are new superseding records; existing ledger rows are immutable.
- Chain corruption and uncertain mutation fail closed.

---

## Task 1: Add Council lifecycle and integrity schemas

**Files:**
- Modify: `app/models.py`
- Create: `tests/test_omega_models.py`

### Step 1: Write failing schema tests

Add tests asserting:

```python
from app.models import CouncilStage, CouncilTrace, IntegrityStatus, SignatureRecord, Verdict

EXPECTED = [
    CouncilStage.OBSERVE,
    CouncilStage.MAP,
    CouncilStage.EVALUATE,
    CouncilStage.GENERATE,
    CouncilStage.CROSS_EXAMINE,
    CouncilStage.STRESS_TEST,
    CouncilStage.SYNTHESIZE,
    CouncilStage.GOVERN,
    CouncilStage.VERDICT,
    CouncilStage.RECORD,
]

def test_council_trace_requires_canonical_stage_order():
    trace = CouncilTrace(stage_order=EXPECTED, completed=EXPECTED)
    assert trace.stage_order == EXPECTED


def test_integrity_defaults_are_explicitly_non_durable():
    status = IntegrityStatus()
    assert status.durable is False
    assert status.chain_valid is False
```

Also assert existing callers can still construct `Verdict` without supplying the new fields.

### Step 2: Run the focused test and confirm RED

Run:

```bash
pytest -q tests/test_omega_models.py
```

Expected: import/schema failures because the new models do not exist.

### Step 3: Extend `app/models.py`

Add:

- `CouncilStage` enum with the ten approved stage names.
- `CouncilStageEvent` with `stage`, `status`, `detail`, and optional bounded metadata.
- `CouncilTrace` with canonical `stage_order`, `completed`, `events`, and `mandatory=True`.
- `CouncilChallenge` for cross-examination/stress-test findings.
- `SignatureRecord` with only public metadata: `algorithm`, `key_id`, `signature_b64`, `verified`, `signer`, `error`.
- `IntegrityStatus` with `schema_version`, `previous_record_hash`, `current_record_hash`, `chain_valid`, `ed25519`, `ml_dsa`, `durable`, `read_after_write_verified`, `status`, `error`.
- Extend `Verdict` with backward-compatible defaults for `request_id`, `council_trace`, `integrity`, and `supersedes_decision_id`.

Do not add raw key fields.

### Step 4: Run focused tests

```bash
pytest -q tests/test_omega_models.py tests/test_governance.py
```

Expected: PASS.

### Step 5: Commit

```bash
git add app/models.py tests/test_omega_models.py
git commit -m "feat: add OMEGA Council lifecycle and integrity models"
```

---

## Task 2: Make specialist routing selective regardless of the legacy Council flag

**Files:**
- Modify: `app/router.py`
- Modify: `tests/test_router.py`

### Step 1: Replace the forced-fanout test with compatibility/security tests

Replace `test_forced_council_routes_all` with tests like:

```python
def test_council_true_does_not_blanket_fan_out_specialists():
    assert route("Evaluate this decision", True) == set()


def test_council_false_cannot_disable_relevant_specialist_routing():
    assert "data_analytics" in route("Analyze dashboard metrics", False)


def test_trivial_request_can_use_zero_external_specialists():
    assert route("Explain what a triangle is") == set()
```

Keep the existing research/code/repository/data analytics tests.

### Step 2: Run focused tests and confirm RED

```bash
pytest -q tests/test_router.py
```

Expected: the old `council=True` blanket fan-out behavior fails the new test.

### Step 3: Simplify `OmegaRouter.route()`

Delete the `if p.council is True: ... add all providers` branch. Keep keyword/capability routing and deduplication only.

The mandatory Council lifecycle belongs in the orchestrator, not in provider fan-out.

### Step 4: Run focused tests

```bash
pytest -q tests/test_router.py
```

Expected: PASS.

### Step 5: Commit

```bash
git add app/router.py tests/test_router.py
git commit -m "refactor: make OMEGA specialist routing relevance based"
```

---

## Task 3: Add deterministic cross-examination and stress-test analysis

**Files:**
- Modify: `app/verification.py`
- Create: `tests/test_omega_verification.py`

### Step 1: Write failing tests

Test these cases:

- two independent valid evidence URLs may be `CORROBORATED`, but not `VERIFIED` merely because two providers agree;
- an explicit contradiction already present in `Claim.contradictions` produces a cross-examination finding;
- failed specialists produce evidence-gap findings;
- unsupported/stale/disputed/unverifiable claims reduce the stress-test confidence ceiling;
- no semantic contradiction is invented from plain-text similarity alone.

Example:

```python
def test_cross_examination_never_promotes_consensus_to_verified():
    claims = verifier.verify(results_from_two_providers_same_claim())
    assert all(c.verification != VerificationStatus.VERIFIED for c in claims)
```

### Step 2: Run focused tests and confirm RED

```bash
pytest -q tests/test_omega_verification.py
```

### Step 3: Implement conservative helpers

Add methods to `EvidenceVerifier`:

```python
def cross_examine(self, results, claims) -> list[CouncilChallenge]: ...
def stress_test(self, claims, challenges) -> list[CouncilChallenge]: ...
```

Rules must be deterministic and evidence-state driven. Do not add a fake semantic contradiction classifier.

### Step 4: Run tests

```bash
pytest -q tests/test_omega_verification.py tests/test_data_analytics.py
```

Expected: PASS.

### Step 5: Commit

```bash
git add app/verification.py tests/test_omega_verification.py
git commit -m "feat: add OMEGA cross examination and stress testing"
```

---

## Task 4: Build the external dual-signer contract

**Files:**
- Create: `app/signing.py`
- Create: `tests/test_omega_signing.py`

### Step 1: Write failing signer-contract tests

Use fake in-memory signer implementations only in tests. Test:

- Ed25519 and ML-DSA are both required;
- both receive exactly the same digest bytes;
- a missing signer fails closed;
- a failed verification fails closed;
- timeouts/errors are returned as bounded integrity errors;
- no API accepts a private key parameter;
- signer auth tokens are not present in `SignatureRecord` or exception strings.

### Step 2: Run and confirm RED

```bash
pytest -q tests/test_omega_signing.py
```

### Step 3: Implement `app/signing.py`

Define:

```python
class Signer(Protocol):
    algorithm: str
    async def sign(self, digest: bytes) -> SignatureRecord: ...
    async def verify(self, digest: bytes, signature: SignatureRecord) -> bool: ...

class ExternalHttpSigner:
    ...

class DualSigner:
    async def sign_and_verify(self, digest: bytes) -> tuple[SignatureRecord, SignatureRecord]: ...
```

Production configuration uses signer endpoint URLs, non-secret key identifiers, and authorization material held only in process environment/secret injection. Do not expose any local-private-key mode.

Use distinct environment namespaces, for example:

- `SARA_ED25519_SIGNER_URL`
- `SARA_ED25519_KEY_ID`
- `SARA_ED25519_SIGNER_TOKEN`
- `SARA_ML_DSA_SIGNER_URL`
- `SARA_ML_DSA_KEY_ID`
- `SARA_ML_DSA_SIGNER_TOKEN`

The token values must never be placed in returned objects or logs.

Do not add a local ML-DSA implementation merely to satisfy tests. If an approved ML-DSA signer is not configured, durable ledger acceptance remains unavailable.

### Step 4: Run focused tests

```bash
pytest -q tests/test_omega_signing.py
```

Expected: PASS.

### Step 5: Commit

```bash
git add app/signing.py tests/test_omega_signing.py
git commit -m "feat: add fail closed Ed25519 and ML-DSA signer contract"
```

---

## Task 5: Add the append-only tamper-evident OMEGA verdict ledger

**Files:**
- Create: `app/ledger.py`
- Modify: `app/memory.py`
- Modify: `tests/test_memory_database.py`
- Create: `tests/test_omega_ledger.py`

### Step 1: Write failing ledger tests

Cover:

1. deterministic canonicalization;
2. genesis record uses a defined zero/genesis previous hash;
3. second record references the first record hash;
4. Ed25519 and ML-DSA sign the same record digest;
5. no row is accepted when either signer fails;
6. SQLite `UPDATE` and `DELETE` against accepted OMEGA records are blocked by triggers;
7. `supersedes_decision_id` references a prior record without modifying it;
8. tampering causes `verify_chain()` to fail;
9. restart reconstructs/verifies the chain head;
10. concurrent appends serialize safely;
11. write/read-back uncertainty does not auto-retry or claim durability.

### Step 2: Run and confirm RED

```bash
pytest -q tests/test_omega_ledger.py
```

### Step 3: Implement `app/ledger.py`

Create a dedicated `OmegaVerdictLedger` rather than expanding conversation-memory responsibilities.

Use SQLite with:

- `PRAGMA journal_mode=WAL`
- `PRAGMA synchronous=FULL`
- `PRAGMA busy_timeout=10000`
- `BEGIN IMMEDIATE` around head-read + append
- an `omega_verdict_ledger` table containing canonical payload, previous hash, current hash, both signature records, supersession metadata, and timestamps;
- `BEFORE UPDATE` and `BEFORE DELETE` triggers that `RAISE(ABORT, 'omega_ledger_append_only')`;
- optional `omega_ledger_quarantine` table for failed signing/integrity attempts, storing bounded non-secret failure metadata only.

Canonicalization must use one routine such as:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
```

Hash input must bind schema version, decision ID, timestamp, previous hash, and canonical verdict payload. Use one documented hash algorithm consistently (SHA-512 is already used elsewhere in SARA and is acceptable here).

Append sequence:

1. verify current chain;
2. calculate canonical bytes and digest;
3. ask both signers to sign the same digest;
4. verify both signatures;
5. insert once;
6. commit;
7. read back by decision ID;
8. re-hash and compare;
9. verify new chain head;
10. only then return `IntegrityStatus(durable=True, ...)`.

If outcome is uncertain after attempted mutation, return/raise a `SUBMISSION_UNVERIFIED`-style integrity result and do not blindly retry.

### Step 4: Preserve compatibility

Keep the legacy `DecisionLedger` API used by existing tests and any historical outcome/lesson flow. Do not silently rewrite old `decisions` rows into the new signed ledger. The mandatory OMEGA coordinator will use `OmegaVerdictLedger` for new finalized Council verdicts; legacy history can remain readable as contextual history.

### Step 5: Run focused tests

```bash
pytest -q tests/test_omega_ledger.py tests/test_memory_database.py
```

Expected: PASS.

### Step 6: Commit

```bash
git add app/ledger.py app/memory.py tests/test_omega_ledger.py tests/test_memory_database.py
git commit -m "feat: add append only dual signed OMEGA verdict ledger"
```

---

## Task 6: Refactor `SaraOmega.solve()` into the mandatory staged Council coordinator

**Files:**
- Modify: `app/orchestrator.py`
- Modify: `app/providers/openai_judge.py`
- Create: `tests/test_omega_orchestrator.py`

### Step 1: Write failing lifecycle tests

Use injected fake providers, fake judge, and fake dual signer/ledger so tests are deterministic and offline.

Required tests:

```python
async def test_every_request_traverses_all_internal_council_stages(): ...
async def test_council_false_still_traverses_all_stages(): ...
async def test_trivial_request_uses_zero_external_specialists_but_full_council(): ...
async def test_only_relevant_specialists_are_called(): ...
async def test_governance_block_prevents_provider_execution_but_not_internal_stage_trace(): ...
async def test_requested_action_is_advisory_and_never_executed_by_council(): ...
async def test_non_durable_reasoning_is_explicit_when_signer_unavailable(): ...
async def test_durable_verdict_requires_successful_record_stage(): ...
```

### Step 2: Run and confirm RED

```bash
pytest -q tests/test_omega_orchestrator.py
```

### Step 3: Refactor the coordinator

Implement explicit stage methods or a small `CouncilCoordinator` boundary rather than one monolithic `solve()` body. The orchestrator must record stage events in order.

Safety behavior for governance:

- `EVALUATE` performs an early policy/risk assessment.
- If the request is blocked, `GENERATE` is recorded as policy-suppressed and no external specialist is called.
- `CROSS_EXAMINE`, `STRESS_TEST`, `SYNTHESIZE`, `GOVERN`, `VERDICT`, and `RECORD` still run with truthful suppressed/blocked state.
- Final `GOVERN` remains authoritative.

This satisfies both “every request traverses the Council” and “do not send blocked requests to unnecessary external providers.”

`SYNTHESIZE` must feed the judge the problem map, assignments/results, verified claims, cross-examination findings, stress-test findings, governance context, and prior bounded decision context. Update the OpenAI judge system contract from the old five-step OMEGA wording to the approved ten-stage semantics.

`RECORD` calls `OmegaVerdictLedger.append()` only after the candidate verdict is assembled. A durable decision ID is assigned only when the signed append succeeds. If it fails, return the reasoning result with `integrity.durable=False` and an explicit integrity status; never claim it was recorded.

### Step 4: Run focused and adjacent tests

```bash
pytest -q tests/test_omega_orchestrator.py tests/test_router.py tests/test_governance.py tests/test_data_analytics.py
```

Expected: PASS.

### Step 5: Commit

```bash
git add app/orchestrator.py app/providers/openai_judge.py tests/test_omega_orchestrator.py
git commit -m "feat: make OMEGA Council mandatory for every SARA request"
```

---

## Task 7: Expose Council and integrity state through the governed gateway

**Files:**
- Modify: `main.py`
- Modify: `tests/test_chatgpt_action_gateway.py`

### Step 1: Add failing gateway tests

Extend solve tests to assert:

- response contains `verdict.council_trace.mandatory == true`;
- all ten stage names are represented;
- sending `"council": false` does not disable stages;
- relevant data analytics request still selects data analytics;
- status endpoint reports Council mode as mandatory and exposes only signer readiness/key IDs, never signer tokens;
- GPT action and test tokens still do not receive owner/admin or direct execution authority.

### Step 2: Run and confirm RED

```bash
pytest -q tests/test_chatgpt_action_gateway.py
```

### Step 3: Update gateway integration

Keep `GPTActionGatewayRequest.council` for backward schema compatibility, but mark/interpret it as deprecated and non-authoritative for internal Council activation.

Add bounded status metadata such as:

```json
{
  "omega_council": {
    "mandatory": true,
    "specialist_routing": "selective",
    "execution_authority": false
  },
  "omega_ledger": {
    "dual_signature_required": true,
    "ed25519_signer_configured": false,
    "ml_dsa_signer_configured": false
  }
}
```

Never expose signer URLs containing credentials, tokens, raw signatures from other records, or private material in generic status.

### Step 4: Run gateway tests

```bash
pytest -q tests/test_chatgpt_action_gateway.py tests/test_chatgpt_oauth_action_schema.py
```

Expected: PASS.

### Step 5: Commit

```bash
git add main.py tests/test_chatgpt_action_gateway.py
git commit -m "feat: expose mandatory OMEGA Council integrity metadata"
```

---

## Task 8: Align documentation and production verification evidence

**Files:**
- Modify: `OMEGA_COUNCIL.md`
- Modify: `BUILD_VERIFICATION.md`
- Potentially update: `MANIFEST.sha256` only through the repository's existing manifest-generation process if one exists; do not hand-edit hashes.

### Step 1: Update Council documentation

Replace the old conditional “Council is invoked when...” semantics with mandatory semantics. Document:

- all ten stages;
- selective external specialists;
- advisory-only Council;
- separate execution plane;
- append-only signed ledger;
- dual Ed25519 + ML-DSA acceptance gate;
- fail-closed non-durable behavior.

### Step 2: Run documentation-sensitive tests

Search for tests asserting the old forced-Council behavior and update only those invalidated by the approved design:

```bash
grep -R "forced_council\|council=True\|council.*all\|Observe, Map, Evaluate, Generate, Act" -n tests app OMEGA_COUNCIL.md
pytest -q
```

Do not change unrelated passing behavior.

### Step 3: Update build verification only from actual results

After tests run, write the measured test count and the exact OMEGA integrity status into `BUILD_VERIFICATION.md`. If external production signers were not exercised, state that explicitly; do not report them as production-verified merely because fake test signers pass.

### Step 4: Commit

```bash
git add OMEGA_COUNCIL.md BUILD_VERIFICATION.md MANIFEST.sha256
git commit -m "docs: document mandatory OMEGA Council acceptance"
```

Omit `MANIFEST.sha256` from the command if the repository has no verified generator or it did not change.

---

## Task 9: Adversarial integrity and secret-leakage gate

**Files:**
- Create: `tests/test_omega_adversarial.py`
- Modify implementation files only if a test exposes a real defect.

### Step 1: Add adversarial tests

Cover:

- forged previous hash;
- changed canonical verdict after signature;
- swapped Ed25519/ML-DSA signature metadata;
- same signature reused against a different digest;
- signer response with wrong algorithm/key ID;
- duplicate decision ID;
- concurrent append race;
- attempted ledger UPDATE/DELETE;
- malformed signer response;
- signer timeout after submission, producing uncertain/non-durable state with no automatic retry;
- `council=false` bypass attempt;
- provider consensus without supporting evidence;
- attempted external action through Council reasoning path;
- secret-like values are absent from serialized verdict, ledger records, logs, and status objects.

### Step 2: Run adversarial suite

```bash
pytest -q tests/test_omega_adversarial.py
```

Expected: PASS before proceeding.

### Step 3: Run source secret scan

Run:

```bash
grep -R -n -E "BEGIN (RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY|sk-[A-Za-z0-9_-]{20,}|SARA_(ED25519|ML_DSA)_.*TOKEN=.*[^$]" app tests docs main.py OMEGA_COUNCIL.md || true
```

Review every match manually; test fixtures may contain intentionally fake markers, but no live credential/private key may be present.

### Step 4: Commit

```bash
git add tests/test_omega_adversarial.py
git commit -m "test: adversarially verify OMEGA Council integrity gates"
```

---

## Task 10: Full regression and completion verification

**Files:**
- No source changes unless verification exposes a defect.
- Update `BUILD_VERIFICATION.md` only with measured final results.

### Step 1: Syntax/compile verification

```bash
python -m compileall -q app main.py
```

Expected: exit 0.

### Step 2: Full offline test suite

```bash
pytest -q
```

Expected: all applicable tests PASS. Existing skipped tests may remain skipped only for their previously documented reason; do not hide new failures by adding skips.

### Step 3: Focused Council acceptance run

```bash
pytest -q \
  tests/test_omega_models.py \
  tests/test_router.py \
  tests/test_omega_verification.py \
  tests/test_omega_signing.py \
  tests/test_omega_ledger.py \
  tests/test_omega_orchestrator.py \
  tests/test_chatgpt_action_gateway.py \
  tests/test_omega_adversarial.py
```

Expected: PASS.

### Step 4: Verify diff scope and secrets

```bash
git diff --check
git status --short
git diff main...HEAD -- app tests main.py OMEGA_COUNCIL.md BUILD_VERIFICATION.md docs/superpowers
```

Confirm:

- no raw private keys;
- no credential values;
- no weakening of governance/authority separation;
- no Council execution code;
- no blanket provider fan-out;
- no silent ML-DSA downgrade;
- no mutation method for accepted ledger records.

### Step 5: Update measured verification evidence and commit

Record actual counts/status in `BUILD_VERIFICATION.md`, then:

```bash
git add BUILD_VERIFICATION.md
git commit -m "chore: record mandatory OMEGA Council verification evidence"
```

### Step 6: Stop before deployment

Do **not** deploy to Railway, AWS, GCP, or Azure as part of this implementation plan. Do not merge to `main` automatically. Report:

- branch name;
- final commit SHA;
- tests run and measured results;
- whether Ed25519 external signer was live-verified;
- whether ML-DSA external signer was live-verified;
- ledger chain test result;
- any remaining production configuration required.

Production rollout is a separate, explicitly authorized release task after code review and signer configuration evidence.
