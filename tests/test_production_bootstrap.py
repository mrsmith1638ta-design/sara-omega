import os

import pytest

import sara_production_bootstrap as bootstrap


def _configure(monkeypatch, tmp_path, *, dedicated=False):
    monkeypatch.setenv("OWNER_TOKEN", "owner-test-token")
    monkeypatch.setenv("SARA_FAILSAFE_MASTER_KEY_HEX", os.urandom(32).hex())
    monkeypatch.setenv("SARA_FAILSAFE_REQUIRED", "true")
    monkeypatch.setenv("SARA_FAILSAFE_ROOT", str(tmp_path))
    monkeypatch.setenv("SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT", "true" if dedicated else "false")
    monkeypatch.setenv("SARA_FAILSAFE_MIN_FREE_BYTES", "1024")
    monkeypatch.delenv("SARA_PRODUCTION_ALLOW_INSECURE_OVERRIDE", raising=False)
    monkeypatch.delenv("SARA_SOURCE_COMMIT_SHA", raising=False)


def test_preflight_checkpoint_and_cross_boot_persistence(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, dedicated=False)
    first = bootstrap.run_preflight()
    assert first["bootstrap_ready"] is True
    assert first["checkpoint_self_test"] is True
    assert first["chain_valid"] is True
    assert first["persistence_observed_across_boots"] is False
    assert first["production_accepted"] is False

    second = bootstrap.run_preflight()
    assert second["bootstrap_ready"] is True
    assert second["persistence_observed_across_boots"] is True
    assert second["persistence_status"] == "PROVEN"
    assert second["production_accepted"] is True


def test_preflight_exposes_valid_source_commit_sha(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, dedicated=False)
    source_sha = "A1" * 20
    monkeypatch.setenv("SARA_SOURCE_COMMIT_SHA", source_sha)

    evidence = bootstrap.run_preflight()

    assert evidence["source_commit_sha"] == source_sha.lower()


@pytest.mark.parametrize("source_sha", [None, "", "abc123", "g" * 40, "1" * 39, "1" * 41])
def test_preflight_omits_invalid_source_commit_sha(monkeypatch, tmp_path, source_sha):
    _configure(monkeypatch, tmp_path, dedicated=False)
    if source_sha is not None:
        monkeypatch.setenv("SARA_SOURCE_COMMIT_SHA", source_sha)

    evidence = bootstrap.run_preflight()

    assert "source_commit_sha" not in evidence


def test_preflight_rejects_missing_owner_token(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, dedicated=False)
    monkeypatch.delenv("OWNER_TOKEN", raising=False)
    with pytest.raises(bootstrap.ProductionPreflightError, match="owner_token_not_configured"):
        bootstrap.run_preflight()


def test_preflight_rejects_ephemeral_root_when_dedicated_mount_required(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, dedicated=True)
    if bootstrap.nearest_mount_point(tmp_path) != bootstrap.Path("/"):
        pytest.skip("test environment provides tmp_path on a dedicated mount")
    with pytest.raises(bootstrap.ProductionPreflightError, match="failsafe_root_not_on_dedicated_mount"):
        bootstrap.run_preflight()


def test_failed_evidence_does_not_expose_secrets(monkeypatch):
    secret = "super-secret-owner-token"
    monkeypatch.setenv("OWNER_TOKEN", secret)
    evidence = bootstrap.failed_evidence(RuntimeError("configuration failed"))
    assert secret not in str(evidence)
    assert evidence["production_accepted"] is False
