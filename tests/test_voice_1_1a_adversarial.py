from pathlib import Path

import pytest
from pydantic import ValidationError

from sara_unified.api.schemas import VoiceAccessibilityJobRequest


@pytest.mark.parametrize(
    "forged",
    [
        {"tenant_id": "forged"},
        {"user_uuid": "00000000-0000-4000-8000-000000000001"},
        {"session_id": "quota-evasion"},
        {"model_id": "attacker-model"},
        {"voice_service_url": "http://attacker.invalid"},
        {"length_scale": 0.1},
        {"pronunciation_rules": {"SARA": "wrong"}},
    ],
)
def test_job_contract_rejects_forged_policy_and_renderer_fields(forged):
    with pytest.raises(ValidationError):
        VoiceAccessibilityJobRequest.model_validate({"text": "Speak safely.", **forged})


def test_user_routes_apply_release_and_access_guards_before_objects():
    source = Path("app/voice_accessibility_http.py").read_text(encoding="utf-8")

    assert "def _authorized_access" in source
    assert "if not store.owns_job(job_id, access)" in source
    assert "Voice accessibility scope rejected" in source
    assert "Voice accessibility entitlement rejected" in source


def test_gateway_never_uses_ip_or_session_as_quota_identity():
    source = Path("app/voice_accessibility_http.py").read_text(encoding="utf-8")
    store_source = Path("app/voice_accessibility.py").read_text(encoding="utf-8")

    assert "client.host" not in source
    assert "session_id" not in source
    assert "client.host" not in store_source
    assert "session_id" not in store_source
