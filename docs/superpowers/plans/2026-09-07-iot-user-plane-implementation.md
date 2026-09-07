# SARA-OMEGA IoT User-Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production IoT user/service plane for SARA-OMEGA that authenticates registered devices, persists real telemetry, evaluates health/anomalies, and executes only explicitly authorized low-risk device commands through verified adapters.

**Architecture:** Add a focused `app/iot/` package mounted through the existing enterprise runtime. The subsystem uses durable SQLite under `SARA_DATA_DIR`, positive capability allow-lists, separate device-control authority, fail-closed ingress, deterministic health analysis, structured command intents, and adapter-specific execution. OMEGA and the High-Level Truth Gate consume IoT evidence without allowing repeated sensor readings or model consensus to become unverified root-cause certainty.

**Tech Stack:** Python 3, FastAPI 0.115.6, Pydantic 2.10.5, SQLite/WAL/FULL durability, httpx 0.28.1, hashlib/hmac, existing SARA-OMEGA OMEGA/Truth Gate/module-awareness/runtime-assurance components. MQTT transport is implemented as a broker-facing ingestion adapter behind the same authenticated telemetry envelope; no fake broker or simulated production device is added.

**Spec:** `docs/superpowers/specs/2026-09-07-iot-user-plane-design.md`

## Global Constraints

- No simulated IoT devices in production.
- No dormant 6G, network-slice, or 3GPP adapters.
- No undocumented claim that SARA can access diagnostics a device or OS does not expose.
- No automatic physical actuation from telemetry alone.
- No broad LAN scanning that implicitly grants trust to discovered devices.
- `GPT_ACTION_TOKEN` and `TEST_TOKEN` must never authorize privileged device control.
- Device-control authority must use a separately scoped credential, `SARA_DEVICE_CONTROL_AUTH_TOKEN`.
- Device registration and capabilities are positive allow-lists; unknown capabilities and commands fail closed.
- Persist all IoT state beneath `SARA_DATA_DIR` using explicit SQLite connection closure and WAL/FULL durability.
- State-changing device commands reserve idempotency before mutation.
- Uncertain device mutation becomes `SUBMISSION_UNVERIFIED` and is never automatically retried.
- Natural-language device diagnoses must pass the High-Level Truth Gate before being presented as factual root-cause conclusions.
- Deployment occurs only from an exact reviewed commit after IoT tests, the full SARA suite, and adversarial gates pass.

---

## File Structure

- Create `app/iot/__init__.py` — package exports.
- Create `app/iot/models.py` — typed device, telemetry, health, command, and decision models.
- Create `app/iot/store.py` — durable SQLite repository and schema.
- Create `app/iot/auth.py` — device authentication, freshness, replay, command authority, and quarantine policy.
- Create `app/iot/telemetry.py` — telemetry validation, retention, persistence, and normalized event processing.
- Create `app/iot/health.py` — deterministic baselines, trends, dropouts, and anomaly evidence.
- Create `app/iot/commands.py` — prepare/execute lifecycle, idempotency, confirmation policy, and uncertainty handling.
- Create `app/iot/adapters/base.py` — strict adapter protocol/result model.
- Create `app/iot/adapters/android.py` — authorized companion-agent bridge for Galaxy S25/Tab S10.
- Create `app/iot/adapters/sony_ht_st5000.py` — verified Sony command bridge with explicit supported-command allow-list.
- Create `app/iot/service.py` — orchestration façade over store/auth/telemetry/health/commands.
- Create `app/iot/router.py` — FastAPI IoT endpoints.
- Modify `app/enterprise_runtime.py` — mount IoT router/service health without changing privileged deployment bridges.
- Modify `app/module_awareness.py` only if needed to persist IoT module registration through existing registry primitives; do not add a second registry mechanism.
- Modify `app/orchestrator.py` — ingest IoT evidence/claims into final truth-gated synthesis when device-health requests enter OMEGA.
- Modify `app/science/truth_gate.py` only to add an IoT-safe evidence classification path if the existing claim API cannot express sensor observation versus root-cause inference.
- Test in `tests/test_iot_models_store.py`, `tests/test_iot_ingress.py`, `tests/test_iot_health.py`, `tests/test_iot_commands.py`, `tests/test_iot_adapters.py`, `tests/test_iot_integration.py`, and `tests/test_iot_adversarial.py`.

---

### Task 1: Typed Models and Durable IoT Store

**Files:**
- Create: `app/iot/__init__.py`
- Create: `app/iot/models.py`
- Create: `app/iot/store.py`
- Test: `tests/test_iot_models_store.py`

**Interfaces:**
- Produces: `DeviceRecord`, `TelemetryEnvelope`, `TelemetryEvent`, `DeviceHealth`, `DeviceCommandIntent`, `CommandRecord`, `CommandStatus`, `CapabilityUnavailable`, `IoTStore`.
- `IoTStore.from_env()` resolves `${SARA_DATA_DIR}/sara_iot.db`.
- `IoTStore.register_device(record: DeviceRecord) -> DeviceRecord`
- `IoTStore.get_device(device_id: str) -> DeviceRecord | None`
- `IoTStore.list_devices() -> list[DeviceRecord]`
- `IoTStore.record_telemetry(event: TelemetryEvent) -> None`
- `IoTStore.recent_telemetry(device_id: str, metric: str | None = None, limit: int = 200) -> list[TelemetryEvent]`
- `IoTStore.reserve_replay(device_id: str, message_id: str, observed_at: str) -> bool`
- `IoTStore.reserve_command(record: CommandRecord) -> CommandRecord`
- `IoTStore.update_command(command_id: str, status: CommandStatus, result: dict | None) -> CommandRecord`

- [ ] **Step 1: Write failing persistence and allow-list tests**

```python
from pathlib import Path
from app.iot.models import DeviceRecord
from app.iot.store import IoTStore


def test_device_registry_persists_across_restart(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    store = IoTStore.from_env()
    record = DeviceRecord(
        device_id="galaxy-s25",
        name="Samsung Galaxy S25",
        device_class="android",
        model="Galaxy S25",
        adapter="android",
        capabilities={"health.read", "battery.read"},
        allowed_commands={"health.query"},
        enabled=True,
    )
    store.register_device(record)
    store.close()
    reopened = IoTStore.from_env()
    assert reopened.get_device("galaxy-s25") == record


def test_unknown_capability_is_not_inferred(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    store = IoTStore.from_env()
    store.register_device(DeviceRecord(
        device_id="sony-ht-st5000",
        name="Sony HT-ST5000",
        device_class="audio",
        model="HT-ST5000",
        adapter="sony_ht_st5000",
        capabilities={"state.read"},
        allowed_commands=set(),
        enabled=True,
    ))
    assert "factory_reset" not in store.get_device("sony-ht-st5000").allowed_commands
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest tests/test_iot_models_store.py -q`

Expected: import/module failures because `app.iot` does not yet exist.

- [ ] **Step 3: Implement models and SQLite schema**

Use Pydantic models with bounded strings/collections and enums. `store.py` must create tables for `devices`, `telemetry_events`, `replay_ids`, `commands`, `health_baselines`, `anomalies`, and `quarantine_events`; set `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=10000`; close every connection using context managers/`closing`.

- [ ] **Step 4: Add bounded-retention tests and implementation**

```python
def test_telemetry_retention_prunes_old_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SARA_IOT_MAX_EVENTS_PER_DEVICE", "3")
    store = IoTStore.from_env()
    # insert four deterministic events
    # assert only newest three remain
```

Implement retention immediately after successful telemetry persistence; do not prune before insert and do not use unbounded `DELETE` statements outside the target device.

- [ ] **Step 5: Run Task 1 tests**

Run: `pytest tests/test_iot_models_store.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add app/iot tests/test_iot_models_store.py
git commit -m "feat: add durable IoT device and telemetry store"
```

---

### Task 2: Device Authentication, Freshness, Replay, Rate Limits, and Quarantine

**Files:**
- Create: `app/iot/auth.py`
- Modify: `app/iot/store.py`
- Test: `tests/test_iot_ingress.py`

**Interfaces:**
- Consumes: `DeviceRecord`, `TelemetryEnvelope`, `IoTStore`.
- Produces: `IoTIngressGuard`.
- `IoTIngressGuard.authenticate_telemetry(envelope: TelemetryEnvelope, supplied_secret: str) -> DeviceRecord`
- `IoTIngressGuard.authorize_control(device: DeviceRecord, supplied_token: str, action: str) -> None`
- Device secrets are compared using `hmac.compare_digest` and stored as salted hashes or externally supplied secrets, never logged in plaintext.

- [ ] **Step 1: Write failing auth/replay tests**

```python
def test_gpt_action_token_cannot_control_device(monkeypatch, guard, device):
    monkeypatch.setenv("GPT_ACTION_TOKEN", "generic-action")
    monkeypatch.setenv("SARA_DEVICE_CONTROL_AUTH_TOKEN", "device-control")
    with pytest.raises(AuthenticationRejected):
        guard.authorize_control(device, "generic-action", "volume.set")


def test_replayed_message_is_rejected(guard, valid_envelope, secret):
    guard.authenticate_telemetry(valid_envelope, secret)
    with pytest.raises(ReplayRejected):
        guard.authenticate_telemetry(valid_envelope, secret)
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_iot_ingress.py -q`

Expected: FAIL because ingress guard is absent.

- [ ] **Step 3: Implement fail-closed guard**

Freshness defaults to 120 seconds and is configurable via `SARA_IOT_FRESHNESS_SECONDS`. Reject disabled/unknown devices, wrong secret, stale/future-skewed events, replayed IDs, disallowed topics, oversized payloads, and rate-limit excess. Track repeated auth/schema failures in the store and quarantine the device for a bounded interval once the configured threshold is reached.

- [ ] **Step 4: Add log-injection/secret-redaction tests**

Assert newline/control characters are normalized and authorization material never appears in emitted structured logs.

- [ ] **Step 5: Run Task 2 tests**

Run: `pytest tests/test_iot_ingress.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add app/iot/auth.py app/iot/store.py tests/test_iot_ingress.py
git commit -m "feat: harden IoT ingress authentication and replay protection"
```

---

### Task 3: HTTPS/MQTT Telemetry Normalization and Health Analysis

**Files:**
- Create: `app/iot/telemetry.py`
- Create: `app/iot/health.py`
- Test: `tests/test_iot_health.py`
- Test: `tests/test_iot_ingress.py`

**Interfaces:**
- `TelemetryService.ingest(envelope: TelemetryEnvelope, supplied_secret: str, transport: str) -> TelemetryEvent`
- `DeviceHealthEngine.evaluate(device_id: str) -> DeviceHealth`
- Health evidence classes: `OBSERVED`, `SUPPORTED`, `UNVERIFIED`.

- [ ] **Step 1: Write failing deterministic health tests**

```python
def test_repeated_temperature_drift_is_supported_not_verified(engine, populated_store):
    health = engine.evaluate("galaxy-s25")
    assert health.classification == "SUPPORTED"
    assert "temperature" in health.evidence_metrics
    assert health.root_cause_verified is False


def test_missing_metric_is_never_invented(engine, populated_store):
    health = engine.evaluate("sony-ht-st5000")
    assert "battery_temperature_c" not in health.observations
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_iot_health.py -q`

- [ ] **Step 3: Implement telemetry normalization**

Accept transport values `https` and `mqtt`. Both paths must create the same trusted `TelemetryEvent` only after the `IoTIngressGuard` succeeds. The MQTT path receives already-decoded broker payload metadata through the same application boundary; no in-process fake broker is added.

- [ ] **Step 4: Implement deterministic health calculations**

Use bounded rolling statistics: current value, median/mean where justified, change from baseline, dropout count, consecutive threshold breaches, and trend slope over recent observations. Device-specific health rules operate only on metrics declared in the device capability/schema metadata.

- [ ] **Step 5: Run health/ingress tests**

Run: `pytest tests/test_iot_ingress.py tests/test_iot_health.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add app/iot/telemetry.py app/iot/health.py tests/test_iot_health.py tests/test_iot_ingress.py
git commit -m "feat: add normalized IoT telemetry and health analysis"
```

---

### Task 4: Governed Command Lifecycle and Device Adapters

**Files:**
- Create: `app/iot/adapters/base.py`
- Create: `app/iot/adapters/android.py`
- Create: `app/iot/adapters/sony_ht_st5000.py`
- Create: `app/iot/commands.py`
- Test: `tests/test_iot_commands.py`
- Test: `tests/test_iot_adapters.py`

**Interfaces:**
- `DeviceAdapter.supported_commands() -> frozenset[str]`
- `DeviceAdapter.execute(intent: DeviceCommandIntent) -> AdapterResult`
- `CommandService.prepare(device_id: str, action: str, parameters: dict, session_id: str, requested_by: str) -> CommandRecord`
- `CommandService.execute(command_id: str, control_token: str, confirmation_token: str | None = None) -> CommandRecord`
- `CommandStatus` includes `PREPARED`, `RESERVED`, `COMPLETED`, `REJECTED`, `SUBMISSION_UNVERIFIED`.

- [ ] **Step 1: Write failing authority/idempotency tests**

```python
def test_unknown_command_rejected_before_adapter_call(command_service):
    with pytest.raises(CapabilityUnavailable):
        command_service.prepare(
            "sony-ht-st5000", "factory_reset", {}, "session-1", "owner"
        )


def test_uncertain_mutation_is_not_retried(command_service, uncertain_adapter, device_token):
    command = command_service.prepare(
        "sony-ht-st5000", "volume.set", {"level": 20}, "session-1", "owner"
    )
    result = command_service.execute(command.command_id, device_token)
    assert result.status == "SUBMISSION_UNVERIFIED"
    with pytest.raises(SubmissionUnverified):
        command_service.execute(command.command_id, device_token)
    assert uncertain_adapter.calls == 1
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_iot_commands.py tests/test_iot_adapters.py -q`

- [ ] **Step 3: Implement strict adapter contract**

`AdapterResult` must distinguish acknowledged success, explicit rejection, capability unavailable, and uncertain transport outcome. Raw natural-language text is never passed to adapters.

- [ ] **Step 4: Implement Android companion-agent adapter**

The server-side adapter uses configured companion-agent HTTPS endpoints and device-scoped bearer credentials. It only exposes actions present in both the registered device allow-list and the companion agent's verified capability document. No ADB, rooting, hidden Android APIs, or undeclared diagnostics are assumed.

- [ ] **Step 5: Implement Sony HT-ST5000 adapter**

Start with only commands proven by repository tests against a configured/verified Sony control interface. If no verified write interface is configured, expose read/reachability state and return `CAPABILITY_UNAVAILABLE` for state-changing actions rather than simulating success.

- [ ] **Step 6: Implement command reservation/confirmation**

Reserve command mutation in SQLite before calling an adapter. Reject reuse of a command/idempotency key with a different request hash. Dangerous/destructive commands are not part of V1 at all.

- [ ] **Step 7: Run Task 4 tests**

Run: `pytest tests/test_iot_commands.py tests/test_iot_adapters.py -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```bash
git add app/iot/adapters app/iot/commands.py tests/test_iot_commands.py tests/test_iot_adapters.py
git commit -m "feat: add governed IoT device command execution"
```

---

### Task 5: IoT Service and FastAPI Surface

**Files:**
- Create: `app/iot/service.py`
- Create: `app/iot/router.py`
- Modify: `app/enterprise_runtime.py`
- Test: `tests/test_iot_integration.py`

**Interfaces:**
- `IoTService.health() -> dict`
- `IoTService.register_device(...)`
- `IoTService.ingest_telemetry(...)`
- `IoTService.device_health(device_id: str)`
- `IoTService.prepare_command(...)`
- `IoTService.execute_command(...)`

- [ ] **Step 1: Write failing API tests**

```python
def test_iot_health_reports_module_presence(client):
    response = client.get("/iot/health")
    assert response.status_code == 200
    body = response.json()
    assert body["module"] == "sara-iot-user-plane"
    assert body["configured"] in {True, False}


def test_registration_rejects_generic_gpt_token(client, monkeypatch):
    monkeypatch.setenv("GPT_ACTION_TOKEN", "generic")
    response = client.post(
        "/iot/devices/register",
        headers={"Authorization": "Bearer generic"},
        json={"device_id": "x", "name": "x", "device_class": "android", "model": "x", "adapter": "android", "capabilities": [], "allowed_commands": [], "enabled": True},
    )
    assert response.status_code in {401, 403}
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_iot_integration.py -q`

- [ ] **Step 3: Implement API routes exactly matching the approved spec**

Implement:
- `GET /iot/health`
- `POST /iot/devices/register`
- `GET /iot/devices`
- `GET /iot/devices/{device_id}`
- `POST /iot/telemetry`
- `GET /iot/devices/{device_id}/health`
- `POST /iot/devices/{device_id}/commands/prepare`
- `POST /iot/devices/{device_id}/commands/execute`
- `GET /iot/devices/{device_id}/commands/{command_id}`

Registration and state-changing routes must use their dedicated authority path; telemetry uses device credentials; read-only device status uses ordinary authenticated SARA user authority as permitted by current policy.

- [ ] **Step 4: Mount the router in `enterprise_runtime.py`**

Instantiate `IoTService` once and include the IoT router using existing runtime patterns. Do not alter `SourceControlBridge` or `RailwayControlBridge`.

- [ ] **Step 5: Run Task 5 tests**

Run: `pytest tests/test_iot_integration.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add app/iot/service.py app/iot/router.py app/enterprise_runtime.py tests/test_iot_integration.py
git commit -m "feat: expose governed IoT runtime API"
```

---

### Task 6: OMEGA, Module Awareness, Runtime Assurance, and Truth Gate Integration

**Files:**
- Modify: `app/orchestrator.py`
- Modify: `app/module_awareness.py` only where the existing registry requires explicit persisted registration
- Modify: `app/runtime_assurance.py` only if required to expose IoT configured/healthy evidence through existing adapter-state mechanics
- Modify: `app/science/truth_gate.py` only if current claim types cannot encode sensor-observation versus root-cause inference
- Test: `tests/test_iot_integration.py`
- Test: `tests/test_iot_health.py`

**Interfaces:**
- IoT health evidence enters OMEGA as structured evidence, not as provider consensus.
- Truth Gate rule: an `OBSERVED` sensor fact may remain observed; causal diagnosis cannot become `VERIFIED` without independent evidence sufficient under existing truth-gate ceilings.

- [ ] **Step 1: Write failing truth-promotion test**

```python
def test_repeated_sensor_readings_do_not_verify_hardware_root_cause(iot_truth_pipeline):
    verdict = iot_truth_pipeline.evaluate(
        observations=[
            {"metric": "battery_temperature_c", "value": 42.0},
            {"metric": "battery_temperature_c", "value": 42.5},
            {"metric": "battery_temperature_c", "value": 43.0},
        ],
        proposed_claim="The battery has physically failed.",
    )
    assert verdict.certainty != "VERIFIED"
    assert verdict.fail_closed is True
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_iot_health.py tests/test_iot_integration.py -q`

- [ ] **Step 3: Wire IoT evidence into OMEGA**

When a device-health problem is routed, attach recent validated observations and `DeviceHealth` evidence to the Council/judge context. Preserve provenance fields including device ID, event IDs, timestamps, metric names, and observation class.

- [ ] **Step 4: Register module-awareness/runtime-assurance evidence**

The runtime reports IoT as present only when `app.iot` imports successfully. `configured=true` requires durable store initialization and required authority configuration for the claimed operation. A read-only configured state must not imply remote-control capability.

- [ ] **Step 5: Run Task 6 tests**

Run: `pytest tests/test_iot_health.py tests/test_iot_integration.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Task 6**

```bash
git add app/orchestrator.py app/module_awareness.py app/runtime_assurance.py app/science/truth_gate.py tests/test_iot_health.py tests/test_iot_integration.py
git commit -m "feat: integrate IoT evidence with OMEGA and truth gating"
```

---

### Task 7: Adversarial Security, Regression, and Acceptance Gates

**Files:**
- Create: `tests/test_iot_adversarial.py`
- Modify: CI/test manifests only if the repository requires explicit test enumeration.

**Interfaces:**
- Produces no new runtime interfaces; verifies all security and acceptance properties.

- [ ] **Step 1: Add adversarial tests**

Cover at minimum:

```python
def test_device_token_cannot_invoke_deployment_control(...): ...
def test_deployment_token_cannot_control_device(...): ...
def test_cross_device_command_authority_is_rejected(...): ...
def test_stale_telemetry_rejected(...): ...
def test_replay_rejected(...): ...
def test_oversized_payload_rejected(...): ...
def test_quarantined_device_cannot_advance_to_analysis(...): ...
def test_log_injection_is_sanitized(...): ...
def test_submitted_unverified_command_is_not_retried(...): ...
def test_unregistered_lan_device_has_no_trust(...): ...
def test_unknown_sony_capability_fails_closed(...): ...
def test_missing_android_metric_is_not_invented(...): ...
```

- [ ] **Step 2: Run IoT suite**

Run: `pytest tests/test_iot_*.py -q`

Expected: all PASS.

- [ ] **Step 3: Run full SARA suite**

Run: `pytest -q`

Expected: all existing tests remain green; pre-existing skips/warnings may remain but no new failures.

- [ ] **Step 4: Compile and secret-scan changed tree**

Run:

```bash
python -m compileall app tests

git diff main...HEAD -- . ':!docs/**' | grep -Ein '(Bearer [A-Za-z0-9._~+/-]{16,}|api[_-]?key\s*=|secret\s*=|token\s*=)' && exit 1 || true
```

Expected: compile succeeds and no credential values appear in diff.

- [ ] **Step 5: Run existing adversarial/build gates**

Use the repository's current CI workflow and Docker/Railway build validation exactly as already configured; do not weaken or bypass any existing gate to make IoT pass.

- [ ] **Step 6: Verify no placeholders/fake capabilities**

Search changed runtime code for `TODO`, `TBD`, `placeholder`, `mock`, `fake`, and unconditional success returns. Any test-only fixtures must remain under `tests/` and cannot register as production devices.

- [ ] **Step 7: Commit acceptance tests**

```bash
git add tests/test_iot_adversarial.py
git commit -m "test: add IoT adversarial and acceptance coverage"
```

---

### Task 8: Review, PR, Exact-Commit Deployment, and Live Acceptance

**Files:**
- No runtime code should change during this task unless review discovers a defect; any defect fix must receive its own test-first commit before proceeding.

**Interfaces:**
- Deployment target remains the existing SARA-OMEGA Railway production service.

- [ ] **Step 1: Review final diff against the design spec**

Confirm every acceptance criterion has executable code and tests. Confirm LG TV, 6G/3GPP, destructive Android actions, and unsupported Sony commands are absent rather than stubbed.

- [ ] **Step 2: Open PR from `design/iot-user-plane-20260907` to `main`**

PR description must list: actual device classes supported, actual adapter capabilities, authority boundaries, persistence location, Truth Gate behavior, and exact tests run.

- [ ] **Step 3: Wait for required CI and inspect all failures**

Do not merge on partial success. Fix failures with new TDD commits and rerun.

- [ ] **Step 4: Merge only reviewed green head**

Record the exact merge SHA.

- [ ] **Step 5: Deploy exact merge SHA through the existing privileged Railway control bridge**

Require expected-current-deployment compare-and-swap and persistent idempotency. Do not reuse generic GPT/test credentials.

- [ ] **Step 6: Live acceptance**

Verify:
- `/health` still reports SARA production healthy;
- `/iot/health` returns module present and truthful configured state;
- registration/control fail closed without dedicated authority;
- a real registered device can submit authenticated telemetry;
- telemetry survives process restart under `/data`/`SARA_DATA_DIR`;
- device health shows observation/inference separation;
- unsupported command returns `CAPABILITY_UNAVAILABLE`;
- uncertain mutation semantics remain `SUBMISSION_UNVERIFIED` with no automatic retry;
- production acceptance remains green.

- [ ] **Step 7: Record deployment evidence**

Capture exact commit SHA, Railway deployment ID, test/CI status, IoT health result, and acceptance result without exposing credentials.

---

## Self-Review

- Spec coverage: registration, device identity, HTTPS/MQTT telemetry, freshness, replay, rate limit/quarantine, durable state, bounded retention, health analysis, Android companion agent, Sony adapter, structured commands, separate action authority, idempotency, `SUBMISSION_UNVERIFIED`, Truth Gate, module awareness, runtime assurance, adversarial testing, and exact-commit deployment are all assigned to tasks above.
- Placeholder scan: runtime tasks explicitly reject placeholders, mocks, fake devices, speculative 6G/3GPP adapters, and unsupported capabilities.
- Type consistency: all later tasks use the Task 1 models/store and Task 4 command/adapter contracts; no duplicate device registry or control authority is introduced.
- Scope integrity: LG TV integration is intentionally excluded until its exact model/control path is known, matching the approved spec.
