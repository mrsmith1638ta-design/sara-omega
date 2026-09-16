# SARA OMEGA Piper Voice Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a governed SARA OMEGA voice-synthesis capability backed by an isolated Piper service using the fixed `sara_elegant_british_v1` profile.

**Architecture:** SARA core owns authorization, input validation, profile selection, audit evidence, and HTTP error mapping. A separate `voice_service` owns the GPL Piper runtime and model; core communicates with it through a narrow `PiperVoiceClient` contract so the main SARA image does not depend on Piper.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, HTTPX, Piper TTS, pytest.

**Spec:** `docs/superpowers/specs/2026-09-15-piper-voice-synthesis-design.md`

## Global Constraints

- Fixed profile ID: `sara_elegant_british_v1`.
- Fixed model ID: `en_GB-cori-high`.
- Main `requirements.txt` MUST NOT add `piper-tts`.
- Piper runtime MUST stay under `voice_service/`.
- SARA audit events MUST NOT persist raw synthesized text.
- SARA-facing callers MUST NOT choose model paths, model IDs, or synthesis parameters in v1.
- Default synthesis values: length scale `1.08`, noise scale `0.55`, noise width scale `0.70`, volume `0.95`.
- Voice is disabled by default and fails closed.

---

### Task 1: Core voice profile and client contract

**Files:**
- Create: `sara_unified/voice/__init__.py`
- Create: `sara_unified/voice/profile.py`
- Create: `sara_unified/voice/client.py`
- Test: `tests/test_voice_synthesis.py`

**Interfaces:**
- Produces: `SARA_VOICE_PROFILE`, `VoiceSynthesisError`, `PiperVoiceClient.synthesize(text: str) -> bytes`.

- [ ] **Step 1: Write the failing profile/client tests**

```python
from sara_unified.voice.profile import SARA_VOICE_PROFILE


def test_sara_voice_profile_is_fixed_british_cori():
    assert SARA_VOICE_PROFILE.profile_id == "sara_elegant_british_v1"
    assert SARA_VOICE_PROFILE.model_id == "en_GB-cori-high"
    assert SARA_VOICE_PROFILE.language == "en-GB"
    assert SARA_VOICE_PROFILE.length_scale == 1.08


def test_piper_client_rejects_empty_audio(monkeypatch):
    from sara_unified.voice.client import PiperVoiceClient, VoiceSynthesisError

    class Response:
        status_code = 200
        content = b""
        headers = {"content-type": "audio/wav"}

    class Client:
        def post(self, *args, **kwargs):
            return Response()
        def __enter__(self): return self
        def __exit__(self, *args): return None

    monkeypatch.setattr("sara_unified.voice.client.httpx.Client", lambda **kwargs: Client())
    client = PiperVoiceClient("http://piper", "secret", timeout_seconds=2)
    try:
        client.synthesize("hello")
        assert False, "expected VoiceSynthesisError"
    except VoiceSynthesisError:
        pass
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `pytest -q tests/test_voice_synthesis.py -k 'profile or empty_audio'`

Expected: import failure because `sara_unified.voice` does not exist.

- [ ] **Step 3: Implement the fixed profile and HTTP client**

`profile.py` defines an immutable `VoiceProfile` dataclass and the exact fixed profile values from the spec. `client.py` posts to `<service_url>/synthesize` with `X-SARA-VOICE-TOKEN`, the fixed synthesis values, a mandatory timeout, and raises `VoiceSynthesisError` on transport errors, non-200 responses, non-WAV content, or empty audio.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `pytest -q tests/test_voice_synthesis.py -k 'profile or empty_audio'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sara_unified/voice tests/test_voice_synthesis.py
git commit -m "feat: add governed Piper voice client"
```

---

### Task 2: SARA configuration and governed API surface

**Files:**
- Modify: `sara_unified/config.py`
- Modify: `sara_unified/api/schemas.py`
- Modify: `sara_unified/app.py`
- Modify: `tests/test_voice_synthesis.py`

**Interfaces:**
- Consumes: `PiperVoiceClient`, `SARA_VOICE_PROFILE`.
- Produces: `POST /v1/voice/synthesize`, `GET /v1/voice/profile`, configuration fields and environment parsing.

- [ ] **Step 1: Add failing API tests**

Tests must prove: unauthorized calls return `401`; disabled voice returns `503`; empty text returns `422`; success returns `audio/wav`; `/v1/voice/profile` returns the fixed profile; capabilities include `voice-synthesis`; audit JSONL contains `text_sha256` and `character_count` but not the raw sentence.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `pytest -q tests/test_voice_synthesis.py`

Expected: route/config assertions fail because the feature is not wired into the app.

- [ ] **Step 3: Implement minimal config and routes**

Add settings with exact defaults from the spec and positive-value validation. Add `VoiceSynthesisRequest(text: str)` with non-empty trimming and max-length enforcement in the route. Extend the default operator permission set with `voice:synthesize`. Add `voice-synthesis` to capability/passport allowlists. Inject a voice client into `SARAUnified` for tests; when enabled without an injected client, construct `PiperVoiceClient` from settings. Return `Response(content=wav, media_type="audio/wav")`. Hash text with SHA-256 and audit only the digest, count, and profile ID.

- [ ] **Step 4: Run focused and unified tests**

Run: `pytest -q tests/test_voice_synthesis.py tests/test_unified_core.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sara_unified/config.py sara_unified/api/schemas.py sara_unified/app.py tests/test_voice_synthesis.py
git commit -m "feat: expose governed SARA voice API"
```

---

### Task 3: Isolated Piper service

**Files:**
- Create: `voice_service/__init__.py`
- Create: `voice_service/app.py`
- Create: `voice_service/requirements.txt`
- Create: `voice_service/Dockerfile`
- Create: `voice_service/README.md`
- Test: `tests/test_voice_service.py`

**Interfaces:**
- Produces: `create_voice_service(engine=None)` and authenticated `POST /synthesize` returning WAV.

- [ ] **Step 1: Write failing service tests**

Tests inject a fake engine with `synthesize(text, *, length_scale, noise_scale, noise_w_scale, volume) -> bytes` and prove: missing token returns `503` at startup/configuration boundary or `401` at request boundary as designed; wrong token returns `401`; correct token returns WAV; empty text returns `422`; `/health` reports readiness only when an engine is loaded.

- [ ] **Step 2: Run service tests and verify RED**

Run: `pytest -q tests/test_voice_service.py`

Expected: import failure because `voice_service` does not exist.

- [ ] **Step 3: Implement service and Piper engine adapter**

Use `piper.PiperVoice.load(PIPER_MODEL_PATH)` inside the service-only module. Use `piper.config.SynthesisConfig` and `wave`/`io.BytesIO` to produce WAV bytes. Require `SARA_VOICE_SERVICE_TOKEN`. Do not accept model names or paths from request JSON.

`voice_service/requirements.txt` contains:

```text
fastapi==0.141.1
uvicorn[standard]==0.34.0
piper-tts==1.8.0
pydantic==2.13.4
```

- [ ] **Step 4: Run tests**

Run: `pytest -q tests/test_voice_service.py`

Expected: PASS without downloading the Cori model because tests inject the fake engine.

- [ ] **Step 5: Commit**

```bash
git add voice_service tests/test_voice_service.py
git commit -m "feat: add isolated Piper voice service"
```

---

### Task 4: Release verification and evidence

**Files:**
- Modify: `.github/workflows/sara-v32-validate.yml` only if existing pytest invocation does not already collect the new tests.
- Modify: `README.md` with the disabled-by-default voice capability and service boundary.

**Interfaces:**
- Produces: CI-verifiable voice feature with no main-image Piper dependency.

- [ ] **Step 1: Run repository verification**

Run:

```bash
pytest -q
python -m compileall -q sara_unified voice_service
python - <<'PY'
from pathlib import Path
main = Path('requirements.txt').read_text()
assert 'piper-tts' not in main
voice = Path('voice_service/requirements.txt').read_text()
assert 'piper-tts==1.8.0' in voice
PY
```

Expected: all commands succeed.

- [ ] **Step 2: Run dependency/security checks used by the repository**

Run the repository's existing validation/security workflow commands without weakening or skipping gates.

- [ ] **Step 3: Document deployment contract**

README must state that voice is disabled until `SARA_VOICE_ENABLED=true`, the internal Piper URL/token are set, and the Cori model is provisioned to the separate service.

- [ ] **Step 4: Commit**

```bash
git add README.md .github/workflows/sara-v32-validate.yml
git commit -m "docs: document SARA Piper voice deployment"
```

- [ ] **Step 5: Open PR and verify CI**

Open a PR from `feature/piper-voice-synthesis` to `main`. Do not claim production acceptance until repository CI and the separate live synthesis transaction have both passed.
