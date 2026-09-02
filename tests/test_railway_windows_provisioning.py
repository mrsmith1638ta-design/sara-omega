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


def test_native_windows_activator_cannot_create_or_link_context() -> None:
    text = _text().lower()
    assert "railway init" not in text
    assert "railway add --service" not in text
    assert '@("link"' not in text
    assert '@("service", $servicename)' not in text
    assert '"--workspace"' not in text
    assert 'railway workspace' not in text


def test_native_windows_activator_uses_explicit_target_tuple() -> None:
    text = _text()
    assert '$targetArgs = @("--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName)' in text
    assert '@("variable", "list") + $targetArgs + @("--kv")' in text
    assert '@("deployment", "list") + $targetArgs + @("--limit", "1", "--json")' in text
    assert '@("up", "--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName, "--ci")' in text


def test_native_windows_volume_context_precedes_subcommand() -> None:
    text = _text()
    assert '$volumeArgs = @("volume", "--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName)' in text
    assert '$volumeArgs + @("add", "--mount-path", "/data", "--json")' in text
    assert 'volume add --service' not in text.lower()
    assert 'SARA_FAILSAFE_ROOT=/data/sara-failsafe' in text


def test_native_windows_preflights_read_only_contract_before_writes() -> None:
    text = _text()
    preflight = text.index('Running non-interactive Railway command-contract preflight')
    token_write = text.index('Invoke-RailwayStdinWrite -Value $gptActionToken')
    failsafe_write = text.index('Applying production fail-safe variables')
    assert preflight < token_write
    assert preflight < failsafe_write
    assert 'Non-interactive Railway command contract VERIFIED' in text


def test_native_windows_activator_preserves_owner_and_failsafe_authority() -> None:
    text = _text()
    assert 'Refusing to invent or rotate owner authority' in text
    assert 'Refusing to invent a replacement key for an accepted production chain' in text
    assert 'variable set OWNER_TOKEN' not in text
    assert 'variable set SARA_FAILSAFE_MASTER_KEY_HEX' not in text


def test_native_windows_activator_only_generates_limited_action_token() -> None:
    text = _text()
    assert 'New-SecureHex -Bytes 48' in text
    assert '"variable", "set", "GPT_ACTION_TOKEN", "--stdin", "--skip-deploys"' in text
    assert '--require-gpt-action-token' in text


def test_native_windows_activator_avoids_powershell7_only_null_coalescing() -> None:
    text = _text()
    assert '??' not in text
