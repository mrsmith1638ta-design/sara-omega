# SARA Android Companion Design

## Goal
Build a simple, safe, production Android companion app for SARA-OMEGA that installs easily on the user's Samsung Galaxy S25 and Samsung Galaxy Tab S10, pairs securely with the deployed SARA IoT service, collects only user-approved Android telemetry, and exposes only low-risk, explicitly allow-listed remote commands.

## Product Principles

1. **Do not destabilize the device.** No root, ADB, bootloader access, device-owner provisioning, hidden Samsung APIs, accessibility-service abuse, factory reset, app deletion, arbitrary shell execution, firmware changes, or privileged settings rewrites.
2. **Easy installation.** One installable APK, one app, one guided pairing flow, no developer tools required on the phone or tablet.
3. **Least privilege.** Request only permissions required for enabled telemetry. Refuse unavailable metrics rather than guessing.
4. **Read/query first.** V1 command scope is limited to health/query/upload actions. No destructive or system-changing commands.
5. **Fail closed.** If device identity, credential storage, TLS, server identity, command authority, schema validation, or capability verification fails, the app does not act.
6. **Battery-conscious operation.** Use WorkManager for periodic background telemetry, default cadence 15 minutes, plus manual "Check Now" / "Send Now" actions.
7. **Per-device isolation.** Galaxy S25 and Galaxy Tab S10 receive separate device IDs, credentials, pairing records, and revocation boundaries.

## Target Devices

Initial production targets:

- Samsung Galaxy S25, Android.
- Samsung Galaxy Tab S10, Android.

The app should be written against standard supported Android APIs so it is not coupled to one Samsung model. Samsung-specific behavior may be used only when publicly documented and unnecessary for core operation.

## Architecture

Create a native Kotlin Android project under a new repository subtree such as `android/sara-companion/`.

Primary components:

### 1. App UI
A single straightforward status-oriented app with:

- Pairing state: Paired / Not paired.
- Device name/model.
- SARA connection health.
- Last successful telemetry upload.
- Last command received/result.
- Permission status.
- Manual `Check Now` / `Send Now` action.
- Unpair/revoke local credential action with confirmation.

No hidden configuration screens are required for normal operation.

### 2. Pairing and Device Identity
The app creates or receives a stable SARA device identity during guided enrollment.

Required properties:

- Device identity is distinct per installation/device.
- Long-lived secret material is stored in Android Keystore-backed storage.
- Secrets are never written to logs, screenshots, analytics, crash breadcrumbs, or plaintext shared preferences.
- Pairing does not reuse SARA GPT, TEST, Railway, source-control, owner, or deployment credentials.
- Loss or revocation of one device must not affect the other registered device.

The production app must not ship with hard-coded credentials.

### 3. Health Collector
Collect only information Android exposes through stable public APIs and that the user has enabled.

Initial telemetry candidates:

- battery percentage;
- charging state / charging source when exposed;
- battery temperature when exposed by Android;
- available/used storage;
- application-visible memory pressure / memory class information;
- network connectivity class/state;
- device uptime / app heartbeat;
- app version, Android version, manufacturer/model;
- last successful SARA synchronization timestamp.

Important rule: the app never invents a metric. Missing or inaccessible information is marked unavailable and omitted from telemetry evidence.

### 4. Telemetry Envelope
The client sends the server's existing IoT telemetry contract over HTTPS.

Each event includes:

- `device_id`;
- unique `message_id`;
- event timestamp;
- schema version;
- allow-listed topic;
- allow-listed metrics;
- authenticated device credential.

The client must generate a fresh message identifier per transmission and avoid replaying an already accepted mutation/message identity.

### 5. Background Scheduling
Use Android WorkManager for background telemetry.

Default policy:

- 15-minute periodic interval where supported by Android scheduling policy;
- network connectivity constraint for uploads;
- exponential/backoff behavior bounded to avoid aggressive battery/network use;
- no infinite busy retry loop;
- manual `Send Now` can request immediate work;
- app remains usable if Android delays background jobs under Doze/battery optimization.

The UI must not claim exact 15-minute execution guarantees because Android may defer background work.

### 6. Capability Document
The companion exposes its own verified capability set to the server-side Android adapter.

Initial V1 command capability list:

- `health.query`
- `battery.query`
- `storage.query`
- `network.query`
- `heartbeat.now`
- `telemetry.send_now`

No generic command execution endpoint exists. Unknown actions are rejected locally.

### 7. Command Handling
Remote instructions are accepted only as structured SARA command objects, never raw natural-language strings.

Lifecycle:

`SARA command -> authenticated client transport -> device-id match -> capability allow-list -> local validation -> action -> acknowledgement -> SARA audit outcome`

V1 commands are read/query/upload operations only. They do not modify Android system state.

A command targeted to one device must not be executable on another device.

### 8. Transport
Use HTTPS only for V1 Android client communication.

Requirements:

- TLS certificate validation enabled;
- no trust-all certificate manager;
- no cleartext HTTP in production;
- bounded connect/read/write timeouts;
- no inbound phone port forwarding;
- no LAN discovery requirement;
- device initiates outbound traffic to SARA.

MQTT support remains a server-side IoT capability but is not required in the first Android APK unless it becomes necessary after measured testing.

### 9. Local Data Storage
Store only the minimum state required:

- pairing status;
- public device identifier;
- protected credential handle/material through Keystore-backed mechanisms;
- last sync metadata;
- bounded local diagnostics needed for the UI.

Do not store full unbounded telemetry history locally. SARA's durable server-side store remains the authoritative telemetry history.

## Android Permissions

The first release must be designed to avoid dangerous permissions wherever practical.

Expected baseline permissions:

- `INTERNET`
- `ACCESS_NETWORK_STATE`

Any additional permission must have a direct feature requirement and be documented in the release review. The app must not request contacts, SMS, call logs, microphone, camera, location, accessibility, notification-listener, device-admin, package installation, or file-all-access privileges for this V1 unless a later separately approved feature requires them.

## Installation Experience

Target user journey:

1. Obtain `SARA-Android-Companion-v1.apk`.
2. Tap the APK.
3. Android prompts the user to allow installation from the chosen source if necessary.
4. Tap Install.
5. Open SARA Companion.
6. Tap Pair with SARA.
7. Complete enrollment.
8. App runs a connection test and displays `Paired` when successful.

No ADB, Android Studio, USB debugging, command line, or root access is required for the user's normal installation flow.

## Build and Signing

Create a standard Gradle Android application build.

Production-release requirements:

- release build type with minification/resource shrinking only if verified safe;
- reproducible dependency declarations;
- no committed signing passwords or private keys;
- APK signing performed using a secure release keystore outside source control;
- debug keys must never be represented as production signing identity;
- artifact named clearly, e.g. `SARA-Android-Companion-v1.apk`.

A locally testable debug APK may be generated during development, but it must be clearly distinguished from the final signed release APK.

## Server Compatibility

The app must integrate with the production SARA IoT framework already present in `app/iot/`.

Compatibility requirements:

- Android companion capability discovery matches the server-side Android adapter contract.
- Telemetry matches `TelemetryEnvelope` schema and registered metric/topic allow-lists.
- Device-specific credentials are compatible with the IoT ingress authentication model.
- Server `SUBMISSION_UNVERIFIED` semantics remain authoritative for uncertain command outcomes.
- Client acknowledgements must never upgrade an unsupported hardware diagnosis to verified root cause.

If server enrollment APIs are insufficient for safe first-run provisioning, add the smallest production-grade enrollment endpoint required under the same dedicated device-control authority boundary. Do not expose generic GPT/TEST credentials to the client.

## Failure Behavior

The app fails safely:

- no network: retain minimal pending state and retry later under WorkManager rules;
- wrong/revoked credential: stop trusted uploads and display pairing/auth error;
- TLS failure: do not connect;
- server 4xx policy rejection: do not blindly retry;
- server 5xx/transient network error: bounded retry/backoff;
- malformed command: reject;
- unsupported command: reject;
- device-id mismatch: reject;
- Keystore failure: treat pairing as unavailable rather than falling back to plaintext secrets;
- unavailable Android metric: omit/mark unavailable rather than fabricate.

## Security Review Requirements

Before release, verify:

- no hard-coded secrets;
- no debug logging of authorization headers or credentials;
- Android network security config prohibits cleartext traffic;
- dependency vulnerability review;
- exported activities/services/receivers are minimized and protected;
- no broad implicit intents that permit unauthorized command injection;
- no WebView-based privileged control plane;
- no arbitrary URL override in production pairing;
- command parser accepts only known structured fields and bounded sizes;
- background work cannot bypass pairing/auth state.

## Testing Requirements

### Unit tests

- telemetry schema generation;
- missing metric behavior;
- capability allow-list;
- credential state transitions;
- command rejection;
- device-id isolation;
- retry/backoff decisions;
- pairing state machine.

### Android instrumentation tests

- first launch;
- pairing UI state;
- Keystore-backed credential persistence;
- app restart persistence;
- manual Send Now;
- offline state and recovery;
- no-crash behavior when telemetry APIs return null/unavailable values.

### Integration tests

Against a controlled SARA environment:

- register S25-class device;
- submit authenticated telemetry;
- reject wrong secret;
- reject replayed message ID;
- capability discovery;
- `health.query`/`battery.query`/`storage.query`/`network.query`/`heartbeat.now`/`telemetry.send_now` command lifecycle;
- one device cannot use another device's identity/credential;
- revoked pairing stops trusted telemetry.

### Release acceptance

- Gradle build succeeds;
- Android lint passes with no unresolved release-blocking findings;
- unit tests pass;
- instrumentation tests pass on supported emulator/device API level;
- release APK installs and launches on Galaxy S25-class Android target;
- compatibility verified for Galaxy Tab S10 target;
- uninstall/reinstall path does not silently resurrect revoked credentials;
- permission review confirms no unnecessary dangerous permissions;
- secret scan of repository/build configuration passes;
- final APK signing verification passes.

## Non-Goals for V1

- screen viewing/control;
- microphone/camera access;
- contact/SMS/call-log access;
- location tracking;
- arbitrary file browsing;
- app installation/removal;
- system setting changes;
- reboot/shutdown;
- Bluetooth/Wi-Fi toggling;
- Android accessibility automation;
- root/ADB/device-owner features;
- Samsung hidden/internal APIs;
- LG TV support;
- Sony soundbar LAN control inside the Android app;
- generic remote desktop behavior.

## Acceptance Criteria

The Android companion is accepted only when:

1. one APK supports both target Samsung Android devices;
2. installation does not require root, ADB, developer mode, Android Studio, or command-line steps on the device;
3. the app requests no unnecessary dangerous permissions;
4. credentials remain protected by Android Keystore-backed storage and are absent from source control/logs;
5. authenticated telemetry reaches SARA's production-compatible IoT contract;
6. telemetry collection never invents unavailable device metrics;
7. 15-minute background monitoring uses WorkManager and does not claim exact execution timing;
8. low-risk command handling is positive-allow-list only;
9. cross-device credential/command reuse is rejected;
10. network/auth/TLS/Keystore failures fail closed;
11. all Android unit, instrumentation, integration, lint, build, security, and signing gates required above pass;
12. the resulting release artifact is a clearly named, signed installable APK suitable for simple user installation.
