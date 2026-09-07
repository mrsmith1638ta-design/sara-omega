# SARA-OMEGA Production IoT User-Plane Design

## Goal
Build a real, production IoT service plane for SARA-OMEGA that ingests and evaluates telemetry from authorized devices, supports governed remote-control commands, and integrates with the existing OMEGA, Truth Gate, module-awareness, runtime-assurance, and audit architecture without introducing placeholders or speculative 6G interfaces.

## Scope
This first production build targets capabilities that are useful now:

- authenticated device registration and identity;
- MQTT and HTTPS telemetry ingress;
- schema validation, freshness checks, replay protection, rate limiting, and quarantine;
- durable device state, telemetry history, and health baselines under `SARA_DATA_DIR`;
- device-health analysis and anomaly detection from observed telemetry;
- governed command execution through explicit per-device adapters;
- text and speech-to-text commands normalized into structured device intents;
- read-only monitoring by default;
- explicit action authority for write/control operations;
- signed/audited command and observation records;
- integration with existing OMEGA reasoning and High-Level Truth Gate for factual claims derived from device data.

The initial hardware targets are the user's Samsung Galaxy S25, Samsung Galaxy Tab S10, and Sony HT-ST5000. LG TV integration is excluded from this first scope until its exact model and supported control path are known.

## Non-Goals

- No simulated IoT devices in production.
- No dormant 6G, network-slice, or 3GPP adapters.
- No undocumented claim that SARA can access diagnostics a device or OS does not expose.
- No automatic physical actuation from telemetry alone.
- No broad LAN scanning that implicitly grants trust to discovered devices.
- No use of `GPT_ACTION_TOKEN` or `TEST_TOKEN` as privileged device-control authority.

## Architecture

### 1. Lean Control Plane
Existing privileged control remains responsible for identity, authentication, authorization, trust state, governance, session state, service admission, and fail-safe policy. IoT device control receives a separate privileged authority boundary rather than inheriting deployment-control credentials.

### 2. IoT User/Service Plane
Create a focused `app/iot/` subsystem with independently testable units:

- `models.py` — device identities, telemetry envelopes, command intents, health state, policy decisions.
- `registry.py` — durable device registry and per-device capability declaration.
- `auth.py` — device authentication, message freshness, anti-replay, and command-authority validation.
- `telemetry.py` — normalized telemetry ingestion and persistence.
- `health.py` — baseline and anomaly evaluation using observed history.
- `commands.py` — structured command validation and execution orchestration.
- `adapters/base.py` — strict adapter protocol.
- `adapters/android.py` — authorized Android companion-agent interface for Galaxy devices.
- `adapters/sony_ht_st5000.py` — only commands verified against supported Sony control paths; unavailable capabilities fail closed.
- `service.py` — IoT application service tying registry, telemetry, health, and commands together.
- `router.py` — FastAPI endpoints mounted into the existing enterprise runtime.

### 3. Device Registry
A device exists in SARA only after explicit registration. Every device record includes:

- stable `device_id`;
- human-readable name;
- device class and model;
- adapter type;
- declared capabilities;
- trust state;
- allowed telemetry topics/endpoints;
- allowed command set;
- command confirmation policy;
- last-seen timestamp;
- health state.

Capabilities are positive allow-lists. Unknown commands are rejected.

### 4. Telemetry Ingress
Telemetry enters through authenticated MQTT or HTTPS. Every envelope must include device identity, monotonic or unique message identifier, event timestamp, schema version, metric payload, and authentication material. The ingress gate checks:

1. device exists and is enabled;
2. authentication succeeds;
3. event is within the allowed freshness window;
4. message identifier has not been seen before;
5. topic/endpoint is allowed for that device;
6. payload matches the declared schema and size limits;
7. rate limits are respected.

Failure is reject or quarantine; malformed input never advances to trusted analysis.

### 5. Durable State
Use SQLite under `SARA_DATA_DIR` with explicit connection closure and WAL/FULL durability patterns compatible with the existing SARA persistence model. Persist:

- devices;
- capabilities;
- telemetry events;
- command requests and outcomes;
- replay identifiers;
- health baselines;
- anomaly records.

Retention is bounded by configurable count/time limits so telemetry cannot grow the database without control.

### 6. Device Health
Health analysis distinguishes observation from inference. Examples:

- `OBSERVED`: battery temperature is 42 C;
- `SUPPORTED`: repeated temperature rise plus discharge-rate drift indicates battery degradation risk;
- `UNVERIFIED`: physical battery failure has not been confirmed.

The health engine may calculate deterministic trends, threshold violations, moving baselines, dropout rates, and device-specific anomaly signals. It must not invent metrics unavailable from the device.

### 7. Truth Gate Integration
Any natural-language diagnosis derived from IoT data is converted into ScienceClaim-equivalent evidence inputs or an IoT claim structure consumed by the High-Level Truth Gate. Sensor observations may support an inference but cannot be promoted to verified hardware failure without stronger evidence. Agreement among repeated readings does not automatically prove root cause.

### 8. Remote-Control Framework
Text or speech-to-text requests are normalized to a structured `DeviceCommandIntent` before execution. Raw natural-language strings are never forwarded to device adapters.

Command lifecycle:

`user text/voice -> intent normalization -> user/session authentication -> device lookup -> capability allow-list -> action authority gate -> optional confirmation -> adapter execution -> device acknowledgement/read-back -> durable audit record`.

Read-only commands may use ordinary authenticated user authority. State-changing commands require a separate `SARA_DEVICE_CONTROL_AUTH_TOKEN` or equivalent separately scoped privileged identity at the trusted bridge boundary. Dangerous commands such as factory reset, account removal, firmware changes, or destructive data operations are excluded from V1.

### 9. Android Integration
Galaxy S25 and Galaxy Tab S10 integration uses an authorized Android companion agent installed by the user. The server never assumes access to Android diagnostics that the agent cannot obtain under Android permissions. The companion agent can send only metrics explicitly enabled by the user and can expose only explicitly allowed actions. Initial useful telemetry should include battery/charging status, temperature where available, storage, memory pressure, connectivity state, uptime/reboot events, and app/agent heartbeat. Initial actions should remain low risk, such as querying health/state and user-approved non-destructive device actions exposed by the agent.

### 10. Sony HT-ST5000 Integration
The Sony adapter is limited to documented or directly verified supported network-control behavior. The adapter exposes only capabilities actually confirmed in implementation/testing. Network reachability, response health, volume/input/state operations may be supported when the verified Sony interface allows them. Any unsupported capability returns `CAPABILITY_UNAVAILABLE`; it is never simulated.

### 11. Security and Containment
Apply SARA's existing adversarial posture:

- separate device-control credentials from owner/GPT/test/deployment-control credentials;
- constant-time credential comparison where appropriate;
- replay prevention;
- bounded payloads and logs;
- secret redaction;
- per-device rate limits;
- quarantine after repeated authentication or schema failures;
- no implicit trust from IP address or LAN membership;
- command idempotency before mutation;
- `SUBMISSION_UNVERIFIED` semantics when a state-changing command may have reached a device but outcome cannot be confirmed;
- no automatic retry after uncertain mutation;
- no cross-device or cross-session authority leakage.

### 12. Existing SARA Integration
The IoT service is mounted through the existing enterprise runtime and registered with module awareness. OMEGA can consume IoT health summaries and evidence when a user asks about a device. Runtime assurance reports whether IoT is configured and healthy. Existing deployment/source-control bridges remain unchanged and cannot be invoked through device-control tokens.

## Initial API Surface

- `GET /iot/health`
- `POST /iot/devices/register`
- `GET /iot/devices`
- `GET /iot/devices/{device_id}`
- `POST /iot/telemetry`
- `GET /iot/devices/{device_id}/health`
- `POST /iot/devices/{device_id}/commands/prepare`
- `POST /iot/devices/{device_id}/commands/execute`
- `GET /iot/devices/{device_id}/commands/{command_id}`

State-changing routes are authenticated and fail closed. Registration and control endpoints are not exposed to generic GPT action credentials.

## Testing Requirements

Tests must cover:

- registration and capability allow-lists;
- valid and invalid device authentication;
- replayed/stale/oversized telemetry;
- malformed schemas and log injection;
- rate-limit and quarantine behavior;
- persistence and restart recovery;
- bounded retention;
- health-baseline calculations;
- unsupported metric non-invention;
- command intent validation;
- unauthorized and cross-device command attempts;
- idempotent command reservation;
- uncertain mutation -> `SUBMISSION_UNVERIFIED` with no retry;
- adapter capability mismatch;
- Truth Gate downgrade of unsupported hardware-failure claims;
- module-awareness registration and runtime-assurance health;
- regression tests proving deployment-control tokens cannot control devices and device tokens cannot deploy.

## Acceptance Criteria

The build is accepted only when:

1. no placeholder service or fake device capability exists;
2. all IoT tests pass locally and in CI;
3. the existing full SARA test suite remains green;
4. adversarial security tests pass;
5. telemetry persists across restart using `SARA_DATA_DIR`;
6. device control fails closed on missing/invalid authority;
7. uncertain device mutations are never automatically retried;
8. Truth Gate prevents unsupported root-cause certainty;
9. live runtime reports IoT capability only when the module is actually present and configured;
10. deployment occurs only from an exact reviewed commit after all prior gates pass.
