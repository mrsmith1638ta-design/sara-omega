from pathlib import Path

SCRIPT = Path("tools/railway_account_provision_windows.ps1")


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_native_windows_activator_is_pinned_to_canonical_production_identity() -> None:
    text = _text()
    assert 'd231d279-92f3-435d-a1d6-c38849b6bfc8' in text
    assert 'sara-omega-production.up.railway.app' in text
    assert '[string]$ServiceName = "sara-omega"' in text
    assert '[string]$EnvironmentName = "production"' in text


def test_native_windows_activator_cannot_create_projects_or_services() -> None:
    text = _text().lower()
    assert "railway init" not in text
    assert "railway add --service" not in text
    assert 'refusing to create a replacement service' in text


def test_native_windows_activator_uses_linked_context_volume_contract() -> None:
    text = _text()
    assert '& railway volume add --mount-path /data --json' in text
    assert 'railway volume add --service' not in text
    assert 'SARA_FAILSAFE_ROOT=/data/sara-failsafe' in text


def test_native_windows_activator_preserves_owner_and_failsafe_authority() -> None:
    text = _text()
    assert 'Refusing to invent or rotate owner authority' in text
    assert 'Refusing to invent a replacement key for an accepted production chain' in text
    assert 'variable set OWNER_TOKEN' not in text
    assert 'variable set SARA_FAILSAFE_MASTER_KEY_HEX' not in text


def test_native_windows_activator_only_generates_limited_action_token() -> None:
    text = _text()
    assert 'New-SecureHex -Bytes 48' in text
    assert 'variable set GPT_ACTION_TOKEN --stdin' in text
    assert '--require-gpt-action-token' in text


def test_native_windows_activator_avoids_powershell7_only_null_coalescing() -> None:
    text = _text()
    assert '??' not in text
