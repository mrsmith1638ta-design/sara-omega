from pathlib import Path

SCRIPT = Path("tools/railway_account_provision_windows.ps1")
FINALIZER = Path("tools/railway_finalize_windows.ps1")


def _text(path: Path = SCRIPT) -> str:
    return path.read_text(encoding="utf-8")


def test_native_windows_activator_is_pinned_to_canonical_production_identity() -> None:
    text = _text()
    assert 'd231d279-92f3-435d-a1d6-c38849b6bfc8' in text
    assert 'sara-omega-production.up.railway.app' in text
    assert '[string]$ServiceName = "sara-omega"' in text
    assert '[string]$EnvironmentName = "production"' in text


def test_native_windows_lane_cannot_create_or_link_context() -> None:
    for text in (_text(), _text(FINALIZER)):
        lower = text.lower()
        assert "railway init" not in lower
        assert "railway add --service" not in lower
        assert '@("link"' not in lower
        assert '@("service", $servicename)' not in lower
        assert '"--workspace"' not in lower
        assert 'railway workspace' not in lower


def test_native_windows_lane_bypasses_npm_powershell_shim() -> None:
    for text in (_text(), _text(FINALIZER)):
        assert 'Get-Command railway.cmd' in text
        assert 'Get-Command railway.exe' in text
        assert '$ErrorActionPreference = "Continue"' in text
        assert '$exitCode = $LASTEXITCODE' in text


def test_native_windows_activator_uses_explicit_target_tuple() -> None:
    text = _text()
    assert '$targetArgs = @("--project", $ProjectId, "--environment", $EnvironmentName, "--service", $ServiceName)' in text
    assert '@("variable", "list") + $targetArgs + @("--kv")' in text
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
    token_write = text.index('Invoke-RailwayStdinWrite')
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


def test_post_deploy_authority_is_live_https_not_deployment_list() -> None:
    activator = _text()
    finalizer = _text(FINALIZER)
    assert 'railway_finalize_windows.ps1' in activator
    assert 'deployment", "list' not in activator
    assert 'deployment", "list' not in finalizer
    assert 'Invoke-WebRequest -Uri "$BaseUrl/health/ready"' in finalizer
    assert 'Invoke-WebRequest -Uri "$BaseUrl/health/production-acceptance"' in finalizer
    assert '--require-gpt-action-token' in finalizer


def test_finalizer_is_read_only_against_railway_configuration() -> None:
    text = _text(FINALIZER)
    assert '"variable", "list"' in text
    assert '"domain", "list"' in text
    assert '"variable", "set"' not in text
    assert '"volume", "add"' not in text
    assert '"up"' not in text


def test_native_windows_lane_avoids_powershell7_only_null_coalescing() -> None:
    assert '??' not in _text()
    assert '??' not in _text(FINALIZER)
