from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "tools" / "railway_account_provision.sh"
WINDOWS = ROOT / "tools" / "railway_account_provision_windows.sh"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_canonical_supports_exact_project_id_without_name_lookup():
    text = _text(CANONICAL)
    assert 'PROJECT_ID_OVERRIDE="${SARA_RAILWAY_PROJECT_ID:-}"' in text
    assert 'Using explicit Railway production project ${PROJECT_ID}' in text
    assert 'railway link --project "$PROJECT_ID" --environment "$ENVIRONMENT_NAME"' in text


def test_explicit_production_project_never_creates_missing_service():
    text = _text(CANONICAL)
    assert 'if [ -n "$PROJECT_ID_OVERRIDE" ]; then' in text
    assert 'refusing to create a replacement service' in text


def test_volume_creation_uses_linked_context_cli_contract():
    text = _text(CANONICAL)
    assert 'railway volume add --mount-path /data --json' in text
    assert 'railway volume add --service' not in text
    assert 'railway volume add -s' not in text


def test_git_bash_path_conversion_is_disabled_for_container_paths():
    canonical = _text(CANONICAL)
    windows = _text(WINDOWS)
    for text in (canonical, windows):
        assert 'MSYS_NO_PATHCONV=1' in text
        assert "MSYS2_ARG_CONV_EXCL='*'" in text


def test_windows_resolver_passes_exact_live_project_id():
    text = _text(WINDOWS)
    assert 'export SARA_RAILWAY_PROJECT_ID="$TARGET_PROJECT_ID"' in text
    assert 'refusing all Railway writes' in text
    assert 'source "$PROVISION_SCRIPT"' in text
