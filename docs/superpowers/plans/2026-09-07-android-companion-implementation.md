# SARA Android Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe, easy-to-install native Android companion APK for Samsung Galaxy S25 and Galaxy Tab S10 that securely pairs with SARA-OMEGA, sends real Android telemetry every ~15 minutes through WorkManager, and handles only low-risk allow-listed commands through an outbound polling channel.

**Architecture:** Add a native Kotlin Android app under `android/sara-companion/` plus the minimum server changes required for one-time device enrollment and outbound-only command delivery. The phone never exposes an inbound listener: it pairs using a short-lived one-time code, stores its device secret with Android Keystore, uploads telemetry over HTTPS, polls for already-authorized low-risk commands, executes them locally, and posts an authenticated acknowledgement. Existing SARA IoT truth, replay, quarantine, durable command state, and `SUBMISSION_UNVERIFIED` semantics remain authoritative.

**Tech Stack:** Android Gradle Plugin 8.7.x, Kotlin 2.0.x, Java 17, compileSdk 35, minSdk 31, AndroidX Core/AppCompat/Activity, Material Components, Lifecycle/ViewModel, WorkManager 2.10.x, OkHttp 4.12.x, kotlinx.serialization 1.7.x, Android Keystore AES-GCM, Python 3/FastAPI/Pydantic/SQLite for the server-side enrollment and queued-command extensions.

**Spec:** `docs/superpowers/specs/2026-09-07-android-companion-design.md`

## Global Constraints

- One APK must support both Samsung Galaxy S25 and Samsung Galaxy Tab S10.
- Normal installation must not require root, ADB, USB debugging, developer mode, Android Studio, or command-line steps on the device.
- No root, bootloader, device-owner, accessibility automation, hidden Samsung APIs, arbitrary shell execution, app install/remove, reboot/shutdown, system-setting mutation, microphone, camera, contacts, SMS, call logs, location, all-files access, or notification-listener capability in V1.
- Android manifest baseline permissions are limited to `INTERNET` and `ACCESS_NETWORK_STATE`; any added permission is a release-blocking review item.
- No cleartext HTTP in production; TLS certificate validation remains enabled and there is no trust-all network path.
- No production credentials, pairing codes, device secrets, signing passwords, or private signing keys may be committed.
- Device credentials are unique per device and stored only as Android-Keystore-protected ciphertext on the client; server stores only the existing salted hash.
- Pairing uses a short-lived, one-time enrollment code. The app never receives or stores `OWNER_TOKEN`, `GPT_ACTION_TOKEN`, `TEST_TOKEN`, Railway/source-control tokens, or `SARA_DEVICE_CONTROL_AUTH_TOKEN`.
- Background monitoring uses WorkManager with a 15-minute periodic request and network constraint. UI copy must say Android may defer scheduled work.
- V1 command capabilities are exactly: `health.query`, `battery.query`, `storage.query`, `network.query`, `heartbeat.now`, `telemetry.send_now`.
- Android command delivery is outbound-only polling from the device; no phone port forwarding, LAN listener, public phone endpoint, or inbound server-to-phone connection.
- Unknown commands, wrong device IDs, expired/reused pairing codes, wrong device secrets, malformed payloads, and unsupported metrics fail closed.
- The app never invents telemetry. Unavailable Android values are omitted from the telemetry payload and shown as unavailable in the UI.
- Server-side hardware diagnosis remains subject to the existing deterministic IoT truth gate; repeated telemetry cannot independently verify a physical hardware failure.
- Release completion requires Android unit tests, server tests, Android lint, APK assembly, manifest/permission inspection, secret scan, and APK signature verification.

---

## File Structure

### Server changes
- Modify `app/iot/models.py` — add pairing and device-poll command request/response models.
- Modify `app/iot/store.py` — durable one-time pairing-code state and queued Android command lookup/acknowledgement helpers.
- Create `app/iot/pairing.py` — pairing-code issuance/claim service.
- Modify `app/iot/commands.py` — support Android outbound queue reservation without server-initiated network calls.
- Modify `app/iot/router.py` — pairing issue/claim plus authenticated device poll/ack routes.
- Modify `app/iot/adapters/android.py` — represent Android as outbound-polling capability, not an inbound public URL.
- Test `tests/test_iot_android_pairing.py` and extend `tests/test_iot_commands.py`, `tests/test_iot_adversarial.py`, `tests/test_iot_integration.py`.

### Android app
- Create `android/sara-companion/settings.gradle.kts` and root `build.gradle.kts`.
- Create `android/sara-companion/gradle.properties` and `.gitignore`.
- Create `android/sara-companion/app/build.gradle.kts`.
- Create `android/sara-companion/app/src/main/AndroidManifest.xml`.
- Create `android/sara-companion/app/src/main/res/xml/network_security_config.xml`.
- Create Kotlin packages under `app/src/main/java/com/saraomega/companion/`:
  - `model/Models.kt` — serialized API/domain models.
  - `security/KeystoreCredentialStore.kt` — AES-GCM Android Keystore credential protection.
  - `network/SaraApi.kt` — bounded HTTPS API client.
  - `pairing/PairingRepository.kt` — one-time enrollment state machine.
  - `telemetry/DeviceTelemetryCollector.kt` — public-API Android telemetry collection.
  - `telemetry/TelemetryRepository.kt` — envelope creation/upload.
  - `telemetry/TelemetryWorker.kt` — periodic/manual WorkManager upload.
  - `commands/CommandCapabilities.kt` — exact positive allow-list.
  - `commands/CommandRepository.kt` — poll, validate, execute read/query/upload actions, acknowledge.
  - `commands/CommandWorker.kt` — periodic bounded poll.
  - `ui/MainActivity.kt`, `ui/MainViewModel.kt`, `ui/MainUiState.kt` — single status/pairing screen.
- Create unit tests under `app/src/test/java/com/saraomega/companion/`.
- Create instrumentation tests under `app/src/androidTest/java/com/saraomega/companion/`.
- Create `.github/workflows/android-companion-validate.yml` — JDK/Gradle Android validation and APK artifact.

---

### Task 1: One-Time Pairing and Outbound Android Command Queue on the Server

**Files:**
- Modify: `app/iot/models.py`
- Modify: `app/iot/store.py`
- Create: `app/iot/pairing.py`
- Modify: `app/iot/commands.py`
- Modify: `app/iot/adapters/android.py`
- Modify: `app/iot/router.py`
- Create: `tests/test_iot_android_pairing.py`
- Modify: `tests/test_iot_commands.py`
- Modify: `tests/test_iot_adversarial.py`

**Interfaces:**
- `PairingCodeRequest(device_class: str="android", model_prefix: str|None=None, ttl_seconds: int=600)`
- `PairingClaimRequest(code: str, name: str, model: str, manufacturer: str, android_version: str, capabilities: set[str], metrics: set[str])`
- `PairingClaimResponse(device_id: str, device_secret: str, server_base_url: str, accepted_commands: set[str], accepted_metrics: set[str])`
- `PairingService.issue(...) -> str` returns a high-entropy display code and stores only its salted hash.
- `PairingService.claim(request) -> PairingClaimResponse` consumes the code exactly once and registers an Android `DeviceRecord`.
- `GET /iot/device/commands/pending` authenticates with `X-SARA-Device-Id` and `X-SARA-Device-Secret` and returns at most 10 reserved commands for that exact device.
- `POST /iot/device/commands/{command_id}/ack` authenticates the same way and accepts only `COMPLETED`, `REJECTED`, or `SUBMISSION_UNVERIFIED` outcomes.
- `CommandService.execute()` for Android reserves the command and returns it without making an inbound network call to the phone.

- [ ] **Step 1: Write failing server pairing tests**

```python
from app.iot.pairing import PairingService, PairingRejected


def test_pairing_code_is_single_use(tmp_path, monkeypatch):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    service = PairingService.for_test()
    code = service.issue(device_class="android", model_prefix="SM-")
    first = service.claim_android(
        code=code,
        name="Tommy Galaxy",
        model="SM-S938U",
        manufacturer="samsung",
        android_version="16",
        capabilities={"health.query", "telemetry.send_now"},
        metrics={"battery_percent", "charging", "storage_free_bytes", "heartbeat"},
    )
    assert first.device_id.startswith("android-")
    assert len(first.device_secret) >= 32
    with pytest.raises(PairingRejected, match="pairing_code_invalid_or_consumed"):
        service.claim_android(
            code=code,
            name="Second Device",
            model="SM-X920",
            manufacturer="samsung",
            android_version="16",
            capabilities={"health.query"},
            metrics={"heartbeat"},
        )
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_iot_android_pairing.py -q`

Expected: FAIL because `app.iot.pairing` and pairing storage do not exist.

- [ ] **Step 3: Implement pairing persistence and service**

Add `pairing_codes(id, code_salt, code_hash, device_class, model_prefix, expires_at, consumed_at, created_at)` to `sara_iot.db`. Generate codes from at least 128 bits of randomness; display as grouped Base32 text, hash with PBKDF2-HMAC-SHA256 before storage, compare in constant time, reject expired/consumed codes, and atomically mark the code consumed in the same transaction that reserves the claim. Generate the device secret server-side with `secrets.token_urlsafe(32)` and pass it once to `IoTStore.register_device()`.

- [ ] **Step 4: Write failing outbound command tests**

```python
def test_android_execute_reserves_without_inbound_network(command_service, android_device, device_control_token):
    command = command_service.prepare(
        android_device.device_id,
        "health.query",
        {},
        "session-1",
        "owner",
    )
    result = command_service.execute(command.command_id, device_control_token)
    assert result.status.value == "RESERVED"
    assert result.result["delivery"] == "DEVICE_POLL"


def test_wrong_device_cannot_poll_reserved_command(client, s25_credentials, tab_credentials, reserved_s25_command):
    response = client.get(
        "/iot/device/commands/pending",
        headers={
            "X-SARA-Device-Id": tab_credentials.device_id,
            "X-SARA-Device-Secret": tab_credentials.secret,
        },
    )
    assert response.status_code == 200
    assert all(item["device_id"] != s25_credentials.device_id for item in response.json()["commands"])
```

- [ ] **Step 5: Implement Android queue reservation, poll, and acknowledgement**

For `adapter == "android"`, `CommandService.execute()` must authenticate the dedicated control token, reserve the command, set result to `{"delivery":"DEVICE_POLL"}`, and return without HTTP-calling the phone. Add store helpers `pending_commands_for_device(device_id, limit=10)` and `acknowledge_device_command(device_id, command_id, status, result)` with strict device binding and terminal-state checks. A second acknowledgement cannot mutate a completed/terminal command.

- [ ] **Step 6: Add router endpoints and adversarial tests**

`POST /iot/pairing/codes` remains protected by `SARA_DEVICE_CONTROL_AUTH_TOKEN`; `POST /iot/pairing/claim` accepts only a valid one-time code. Device poll/ack routes accept only the per-device secret and never generic GPT/owner/deployment credentials. Add tests for expired code, reused code, model-prefix mismatch, cross-device poll, cross-device ack, malformed ack, and secret redaction.

- [ ] **Step 7: Run server IoT suite**

Run: `pytest tests/test_iot_*.py -q`

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add app/iot tests/test_iot_android_pairing.py tests/test_iot_commands.py tests/test_iot_adversarial.py tests/test_iot_integration.py
git commit -m "feat: add secure Android pairing and outbound command queue"
```

---

### Task 2: Android Project, Manifest Safety, and API Models

**Files:**
- Create: `android/sara-companion/settings.gradle.kts`
- Create: `android/sara-companion/build.gradle.kts`
- Create: `android/sara-companion/gradle.properties`
- Create: `android/sara-companion/.gitignore`
- Create: `android/sara-companion/app/build.gradle.kts`
- Create: `android/sara-companion/app/src/main/AndroidManifest.xml`
- Create: `android/sara-companion/app/src/main/res/xml/network_security_config.xml`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/model/Models.kt`
- Create: `android/sara-companion/app/src/test/java/com/saraomega/companion/model/ModelsTest.kt`

**Interfaces:**
- Package/application ID: `com.saraomega.companion`
- `PairingClaim`, `PairingClaimResponse`, `TelemetryEnvelope`, `PendingCommand`, `CommandAck`, `CapabilityDocument`, `ConnectionState` are `@Serializable` Kotlin data classes.
- Production base URL is build-configured as `https://sara-omega-production.up.railway.app/`; no runtime arbitrary URL field in release UI.

- [ ] **Step 1: Create Gradle project and failing model tests**

```kotlin
@Test
fun telemetryEnvelopeSerializesServerFieldNames() {
    val envelope = TelemetryEnvelope(
        deviceId = "android-123",
        messageId = "msg-12345678",
        eventTimestamp = "2026-09-07T23:00:00Z",
        schemaVersion = "1",
        topic = "telemetry",
        metrics = mapOf("battery_percent" to JsonPrimitive(80)),
    )
    val json = Json.encodeToString(envelope)
    assertTrue(json.contains("\"device_id\""))
    assertTrue(json.contains("\"message_id\""))
}
```

- [ ] **Step 2: Run RED**

Run from `android/sara-companion`: `./gradlew testDebugUnitTest`

Expected: FAIL until models and serialization names exist.

- [ ] **Step 3: Implement project configuration and models**

Use `compileSdk=35`, `minSdk=31`, `targetSdk=35`, Java/Kotlin target 17, ViewBinding, BuildConfig, WorkManager, OkHttp, kotlinx.serialization, lifecycle/viewmodel, and Material Components. Manifest contains only `INTERNET` and `ACCESS_NETWORK_STATE`; `android:usesCleartextTraffic="false"`; exported components are limited to the launcher activity.

- [ ] **Step 4: Run unit test and manifest assertions**

Run:

```bash
./gradlew testDebugUnitTest
./gradlew processDebugMainManifest
```

Then inspect merged manifest and assert it contains no dangerous permissions listed in the spec.

- [ ] **Step 5: Commit Task 2**

```bash
git add android/sara-companion
git commit -m "feat: scaffold safe SARA Android companion"
```

---

### Task 3: Android Keystore Credential Store and Pairing State Machine

**Files:**
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/security/KeystoreCredentialStore.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/network/SaraApi.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/pairing/PairingRepository.kt`
- Test: `android/sara-companion/app/src/test/java/com/saraomega/companion/pairing/PairingRepositoryTest.kt`
- Instrumentation test: `android/sara-companion/app/src/androidTest/java/com/saraomega/companion/security/KeystoreCredentialStoreTest.kt`

**Interfaces:**
- `CredentialStore.save(deviceId: String, deviceSecret: String)`
- `CredentialStore.load(): DeviceCredentials?`
- `CredentialStore.clear()`
- `SaraApi.claimPairing(code: String, device: DeviceDescriptor): PairingClaimResponse`
- `PairingRepository.claim(code: String): PairingState`
- `PairingState` is `Unpaired | Pairing | Paired(deviceId) | Error(message)`.

- [ ] **Step 1: Write failing pairing repository test**

```kotlin
@Test
fun successfulClaimPersistsSecretButStateExposesOnlyDeviceId() = runTest {
    val api = FakeSaraApi(PairingClaimResponse("android-1", "super-secret", setOf("health.query"), setOf("heartbeat")))
    val store = FakeCredentialStore()
    val repo = PairingRepository(api, store, FakeDeviceDescriptorProvider())

    val state = repo.claim("ABCD-EFGH")

    assertEquals(PairingState.Paired("android-1"), state)
    assertEquals("super-secret", store.saved?.deviceSecret)
    assertFalse(state.toString().contains("super-secret"))
}
```

- [ ] **Step 2: Run RED, then implement `SaraApi` and repository**

Use OkHttp with 10s connect/read/write timeouts, JSON content type, no interceptor that logs headers/body, and error mapping: 4xx pairing policy errors are terminal; IO/5xx are retryable only where the caller explicitly allows it.

- [ ] **Step 3: Implement Android Keystore AES-GCM storage**

Generate a non-exportable AES-256 key in `AndroidKeyStore` with `PURPOSE_ENCRYPT|PURPOSE_DECRYPT`, GCM, no user-auth requirement. Encrypt the secret with a random IV; store only `device_id`, IV, and ciphertext in private app preferences. On keystore decrypt failure, return a hard pairing error and never fall back to plaintext.

- [ ] **Step 4: Run unit and instrumentation tests**

Run:

```bash
./gradlew testDebugUnitTest
./gradlew connectedDebugAndroidTest
```

Expected: pairing tests and Keystore restart-persistence tests PASS on an emulator/device.

- [ ] **Step 5: Commit Task 3**

```bash
git add android/sara-companion/app/src
git commit -m "feat: add secure Android pairing and Keystore credentials"
```

---

### Task 4: Real Android Telemetry and WorkManager Scheduling

**Files:**
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/telemetry/DeviceTelemetryCollector.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/telemetry/TelemetryRepository.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/telemetry/TelemetryWorker.kt`
- Test: `android/sara-companion/app/src/test/java/com/saraomega/companion/telemetry/DeviceTelemetryCollectorTest.kt`
- Test: `android/sara-companion/app/src/test/java/com/saraomega/companion/telemetry/TelemetryRepositoryTest.kt`
- Instrumentation test: `android/sara-companion/app/src/androidTest/java/com/saraomega/companion/telemetry/TelemetryWorkerTest.kt`

**Interfaces:**
- `DeviceTelemetryCollector.collect(): Map<String, JsonPrimitive>`
- Metrics: `battery_percent`, `charging`, `battery_temperature_c` only when exposed, `storage_free_bytes`, `storage_total_bytes`, `memory_low`, `network_connected`, `network_transport`, `uptime_ms`, `heartbeat`, `android_version`, `manufacturer`, `model`, `app_version`.
- `TelemetryRepository.sendNow(): SendResult`
- `TelemetryWorker.schedule(context)` uses `PeriodicWorkRequestBuilder<TelemetryWorker>(15, TimeUnit.MINUTES)` with `NetworkType.CONNECTED` and bounded exponential backoff.

- [ ] **Step 1: Write failing unavailable-metric test**

```kotlin
@Test
fun unavailableBatteryTemperatureIsOmitted() {
    val collector = DeviceTelemetryCollector(platform = fakePlatform(batteryTemperatureC = null))
    val metrics = collector.collect()
    assertFalse(metrics.containsKey("battery_temperature_c"))
}
```

- [ ] **Step 2: Implement public-API collectors**

Use `BatteryManager`, sticky `ACTION_BATTERY_CHANGED` only for battery state/temperature, `StatFs` for app-visible storage volume, `ActivityManager.MemoryInfo` for memory pressure, `ConnectivityManager` for current validated network transport, `SystemClock.elapsedRealtime()` for uptime, and `Build`/package metadata for device/app info. Do not introduce runtime permissions beyond the two manifest permissions.

- [ ] **Step 3: Implement telemetry envelope and upload**

Generate a new UUID message ID for each upload, UTC ISO-8601 timestamp, topic `telemetry`, schema `1`, and only server-accepted metrics. Send device ID and secret using the existing telemetry headers/contract; do not persist full telemetry history locally.

- [ ] **Step 4: Implement WorkManager scheduling and retry policy**

Return `Result.failure()` for 4xx auth/schema rejections, `Result.retry()` only for IO/5xx with WorkManager backoff, and `Result.success()` on 2xx. Manual Send Now uses `OneTimeWorkRequest` with the same constraints.

- [ ] **Step 5: Run telemetry tests**

Run:

```bash
./gradlew testDebugUnitTest
./gradlew connectedDebugAndroidTest
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add android/sara-companion/app/src
git commit -m "feat: add real Android telemetry and scheduled uploads"
```

---

### Task 5: Low-Risk Command Polling and Local Execution

**Files:**
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/commands/CommandCapabilities.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/commands/CommandRepository.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/commands/CommandWorker.kt`
- Test: `android/sara-companion/app/src/test/java/com/saraomega/companion/commands/CommandRepositoryTest.kt`

**Interfaces:**
- `CommandCapabilities.ALLOWED` is exactly the six V1 commands.
- `CommandRepository.pollAndExecute(): PollResult`
- Query actions read the current `DeviceTelemetryCollector` snapshot; `telemetry.send_now` delegates to `TelemetryRepository.sendNow()`.
- Every acknowledgement includes the same command ID and terminal outcome `COMPLETED`, `REJECTED`, or `SUBMISSION_UNVERIFIED`.

- [ ] **Step 1: Write failing unknown-command/device-mismatch tests**

```kotlin
@Test
fun unknownCommandIsRejectedWithoutExecution() = runTest {
    val command = PendingCommand("cmd-1", "android-1", "factory_reset", emptyMap())
    val result = repo.execute(command)
    assertEquals(AckStatus.REJECTED, result.status)
    assertEquals(0, fakeTelemetry.sendCalls)
}

@Test
fun commandForAnotherDeviceIsRejected() = runTest {
    val command = PendingCommand("cmd-2", "android-other", "health.query", emptyMap())
    val result = repo.execute(command)
    assertEquals(AckStatus.REJECTED, result.status)
}
```

- [ ] **Step 2: Implement exact allow-list and structured execution**

No raw natural-language command field is executed. `health.query`, `battery.query`, `storage.query`, and `network.query` return subsets of the current public-API telemetry snapshot; `heartbeat.now` returns uptime/heartbeat; `telemetry.send_now` triggers the existing upload path. No action mutates Android system state.

- [ ] **Step 3: Implement polling worker**

Use a network-constrained periodic worker. Fetch at most 10 pending commands, process sequentially, ack each exactly once, and stop/retry conservatively on transport uncertainty. If local execution may have occurred but ack delivery outcome is unknown, persist only the command ID + `SUBMISSION_UNVERIFIED` pending-ack marker and never re-execute that command.

- [ ] **Step 4: Run command tests**

Run: `./gradlew testDebugUnitTest`

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add android/sara-companion/app/src
git commit -m "feat: add fail-closed Android command polling"
```

---

### Task 6: Simple One-Screen UI and Install Flow

**Files:**
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/ui/MainUiState.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/ui/MainViewModel.kt`
- Create: `android/sara-companion/app/src/main/java/com/saraomega/companion/ui/MainActivity.kt`
- Create: `android/sara-companion/app/src/main/res/layout/activity_main.xml`
- Create/update string/theme resources under `app/src/main/res/values/`.
- Instrumentation test: `android/sara-companion/app/src/androidTest/java/com/saraomega/companion/ui/MainActivityTest.kt`

**Interfaces:**
- UI displays: pairing state, model, connection state, last successful upload, last command result, permission/network state, and buttons `Pair with SARA`, `Check Now`, `Send Now`, `Unpair`.
- Pairing accepts one grouped code string. Release UI has no editable server URL.

- [ ] **Step 1: Write failing UI state tests**

Verify fresh install shows `Not paired`, paired install hides secret material, offline state says `Offline — SARA will retry when Android allows`, and schedule copy says `About every 15 minutes; Android may defer background work`.

- [ ] **Step 2: Implement ViewModel and status screen**

Keep the screen intentionally simple: status cards/rows plus four actions. Unpair requires a confirmation dialog, clears Keystore credential state, cancels named WorkManager jobs, and leaves server-side revocation as a separate authenticated management action rather than pretending local deletion revokes the server record.

- [ ] **Step 3: Add accessibility and no-secret-display tests**

All buttons have labels/content descriptions; no device secret, auth header, pairing code after successful claim, or raw exception containing credentials appears in UI state.

- [ ] **Step 4: Run instrumentation tests**

Run: `./gradlew connectedDebugAndroidTest`

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add android/sara-companion/app/src
git commit -m "feat: add simple SARA companion pairing and status UI"
```

---

### Task 7: Android CI, Security Gates, and Installable APK Artifact

**Files:**
- Create: `.github/workflows/android-companion-validate.yml`
- Modify: `android/sara-companion/app/build.gradle.kts` only for deterministic artifact naming/signing configuration.
- Create: `android/sara-companion/scripts/verify_manifest.sh`
- Create: `android/sara-companion/scripts/verify_apk.sh`

**Interfaces:**
- CI artifact name: `SARA-Android-Companion-v1-debug-installable` for the automatically generated installable debug APK.
- Production release signing reads `SARA_ANDROID_KEYSTORE_FILE`, `SARA_ANDROID_KEYSTORE_PASSWORD`, `SARA_ANDROID_KEY_ALIAS`, `SARA_ANDROID_KEY_PASSWORD` only from external CI/local environment; no fallback embedded release key.
- Final release artifact name when signing material is present: `SARA-Android-Companion-v1.apk`.

- [ ] **Step 1: Add Android validation workflow**

Use `actions/checkout@v4`, `actions/setup-java@v4` with Temurin 17, Gradle setup, then run:

```bash
cd android/sara-companion
./gradlew testDebugUnitTest lintDebug assembleDebug
./scripts/verify_manifest.sh
./scripts/verify_apk.sh app/build/outputs/apk/debug/app-debug.apk
```

Upload the debug APK as a GitHub Actions artifact. Debug APK is explicitly labeled installable test build, not production release identity.

- [ ] **Step 2: Implement permission/security verification scripts**

`verify_manifest.sh` fails if merged manifest contains any permission outside `android.permission.INTERNET` and `android.permission.ACCESS_NETWORK_STATE`, any exported non-launcher component, or `usesCleartextTraffic=true`. `verify_apk.sh` runs `apksigner verify --verbose --print-certs`, checks ZIP contents for obvious committed token patterns, and confirms package ID `com.saraomega.companion`.

- [ ] **Step 3: Add conditional release signing**

Configure release signing only when all four external signing inputs exist. If absent, `assembleRelease` is not reported as a production release. When present, run `assembleRelease`, `apksigner verify`, rename to `SARA-Android-Companion-v1.apk`, and upload as a separate release artifact.

- [ ] **Step 4: Run local Android gates**

Run:

```bash
cd android/sara-companion
./gradlew testDebugUnitTest lintDebug assembleDebug
./scripts/verify_manifest.sh
./scripts/verify_apk.sh app/build/outputs/apk/debug/app-debug.apk
```

Expected: all exit 0.

- [ ] **Step 5: Commit Task 7**

```bash
git add .github/workflows/android-companion-validate.yml android/sara-companion
git commit -m "ci: validate and package SARA Android companion"
```

---

### Task 8: Full Integration, Adversarial Review, PR, and APK Handoff

**Files:**
- Modify only defects discovered by verification, each with a failing test first.

**Interfaces:**
- No new interfaces; this task proves the complete system.

- [ ] **Step 1: Run full server and Android verification**

```bash
pytest -q
python tools/adversarial_gate.py
cd android/sara-companion
./gradlew testDebugUnitTest lintDebug assembleDebug
./scripts/verify_manifest.sh
./scripts/verify_apk.sh app/build/outputs/apk/debug/app-debug.apk
```

If an Android emulator/device is available:

```bash
./gradlew connectedDebugAndroidTest
```

No gate may be weakened or skipped to obtain green status; unavailable instrumentation hardware must be reported explicitly rather than falsely marked passing.

- [ ] **Step 2: Secret and forbidden-capability scan**

Run repository diff scans for hard-coded bearer tokens, secrets, signing passwords, private keys, `MANAGE_EXTERNAL_STORAGE`, `BIND_ACCESSIBILITY_SERVICE`, device-admin receivers, `REQUEST_INSTALL_PACKAGES`, microphone/camera/location/contact/SMS permissions, `Runtime.exec`, `ProcessBuilder`, ADB/root strings in runtime code, and cleartext URLs. Runtime occurrences cause failure unless they are explicit rejection tests/docs.

- [ ] **Step 3: Open PR to `main`**

PR description must state: one-time pairing design, outbound-only phone networking, exact telemetry metrics, exact six commands, manifest permissions, test counts, lint result, APK artifact/signature state, and any instrumentation limitation.

- [ ] **Step 4: Require green GitHub CI and review before merge**

Inspect both existing SARA validation and the new Android companion workflow. Fix any failure with test-first commits. Do not merge with a pending/failed Android workflow.

- [ ] **Step 5: Merge exact reviewed head and verify `main` SHA**

Use expected-head merge protection. Record merge SHA and rerun/confirm required main-branch validation if configured.

- [ ] **Step 6: Deploy only the server-side pairing/queue changes to Railway**

Deploy exact merge SHA to the existing `sara-omega-council` service. Confirm `/health` succeeds and live `/iot/health` remains truthful. Do not configure or expose signing keys on Railway.

- [ ] **Step 7: Obtain the APK artifact and verify installability**

Download the GitHub Actions debug-installable APK artifact (or release artifact when external signing material is configured), verify SHA-256 and `apksigner`, and provide the resulting APK as the phone-install artifact. Do not call a debug-signed APK a production-release-signed artifact.

- [ ] **Step 8: Pair the Galaxy S25 safely**

Issue a fresh one-time pairing code through the dedicated server authority, install/open the APK, enter the code, confirm `Paired`, trigger `Send Now`, and verify real telemetry appears server-side. Do not reuse this code for the Tab S10; it receives its own code/device secret.

---

## Self-Review

- **Spec coverage:** easy single-APK install, S25/Tab S10 support, no root/ADB/device-admin, minimal permissions, Keystore protection, one-time pairing, public-API telemetry, 15-minute WorkManager schedule, manual Send Now, exact low-risk command allow-list, outbound-only networking, device isolation, bounded retries, fail-closed behavior, CI/lint/tests, secret scan, signing verification, and APK artifact handoff are each assigned to tasks above.
- **Architecture correction:** the existing server Android adapter used a server-to-device HTTPS endpoint, which conflicts with the approved no-inbound-phone design. Task 1 explicitly replaces that assumption with an authenticated device-poll queue while retaining SARA's reserved/idempotent command semantics.
- **Pairing correction:** the existing `/iot/devices/register` requires `SARA_DEVICE_CONTROL_AUTH_TOKEN`, which must never be placed in the APK. Task 1 adds a short-lived one-time enrollment capability so the app receives only its own per-device secret.
- **Placeholder scan:** no runtime task relies on TODO/TBD, fake devices, simulated telemetry, arbitrary command execution, hidden Android APIs, or unimplemented production stubs.
- **Type consistency:** server pairing output maps directly to Android `PairingClaimResponse`; device ID/secret feed telemetry and command polling; server `RESERVED` maps to device-poll delivery; terminal acknowledgements map to existing `COMPLETED`, `REJECTED`, and `SUBMISSION_UNVERIFIED` statuses.
- **Signing truthfulness:** an automatically built debug-signed APK is installable but not called a production release. Production release signing is accepted only when externally supplied signing material is present and `apksigner` verifies it.
