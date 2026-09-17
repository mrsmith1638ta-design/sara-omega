from pydantic import ValidationError
import pytest

from sara_unified.api.schemas import (
    VoiceAccessibilityEntitlementRequest,
    VoiceAccessibilityJobRequest,
    VoiceAccessibilityPreferencesRequest,
)
from sara_unified.config import Settings


def test_voice_1_1a_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SARA_VOICE_1_1A_ENABLED", raising=False)

    assert Settings.from_env().voice_1_1a_enabled is False


@pytest.mark.parametrize(
    "name",
    [
        "SARA_VOICE_1_1A_USER_JOBS_PER_MINUTE",
        "SARA_VOICE_1_1A_USER_JOBS_PER_DAY",
        "SARA_VOICE_1_1A_USER_CHARACTERS_PER_DAY",
        "SARA_VOICE_1_1A_TENANT_JOBS_PER_MINUTE",
        "SARA_VOICE_1_1A_TENANT_JOBS_PER_DAY",
        "SARA_VOICE_1_1A_TENANT_CHARACTERS_PER_DAY",
        "SARA_VOICE_1_1A_USER_CONCURRENCY",
        "SARA_VOICE_1_1A_TENANT_CONCURRENCY",
        "SARA_VOICE_1_1A_LEASE_SECONDS",
    ],
)
def test_voice_1_1a_limits_are_positive(monkeypatch, name):
    monkeypatch.setenv(name, "0")

    with pytest.raises(ValueError, match=name):
        Settings.from_env()


def test_accessibility_job_rejects_caller_owned_tenant_and_unknown_controls():
    with pytest.raises(ValidationError):
        VoiceAccessibilityJobRequest.model_validate(
            {"text": "Hello.", "tenant_id": "forged", "length_scale": 0.5}
        )


def test_accessibility_preferences_enforce_retention_contract():
    valid = VoiceAccessibilityPreferencesRequest(
        speech_rate="slower",
        preserve_transcript=True,
        transcript_retention_seconds=3600,
    )

    assert valid.transcript_retention_seconds == 3600
    with pytest.raises(ValidationError):
        VoiceAccessibilityPreferencesRequest(
            speech_rate="normal",
            preserve_transcript=False,
            transcript_retention_seconds=3600,
        )


def test_entitlement_request_forbids_tenant_selection():
    with pytest.raises(ValidationError):
        VoiceAccessibilityEntitlementRequest.model_validate(
            {"public_user_id": "SARA-U-ABC", "tenant_id": "forged"}
        )
