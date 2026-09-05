from pathlib import Path


WORKFLOW = Path(".github/workflows/sara-v32-validate.yml")


def test_validation_workflow_has_pinned_gitleaks_secret_scan() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in workflow
    assert "Secret scan" in workflow
    assert "gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
