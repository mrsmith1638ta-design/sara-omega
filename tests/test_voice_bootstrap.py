import hashlib

import pytest


def test_bootstrap_downloads_missing_cori_assets_and_verifies_digest(tmp_path, monkeypatch):
    import voice_service.bootstrap as bootstrap

    expected_bytes = b"verified-cori-model"
    monkeypatch.setattr(bootstrap, "EXPECTED_MODEL_SHA256", hashlib.sha256(expected_bytes).hexdigest())
    calls = []

    def downloader(url, destination):
        calls.append((url, destination.name))
        if destination.name.endswith(".onnx"):
            destination.write_bytes(expected_bytes)
        else:
            destination.write_text('{"audio": {"sample_rate": 22050}}', encoding="utf-8")

    model, config = bootstrap.ensure_cori_model(tmp_path, downloader=downloader)

    assert model.name == "en_GB-cori-high.onnx"
    assert config.name == "en_GB-cori-high.onnx.json"
    assert model.read_bytes() == expected_bytes
    assert [name for _, name in calls] == ["en_GB-cori-high.onnx", "en_GB-cori-high.onnx.json"]


def test_bootstrap_reuses_verified_persistent_assets(tmp_path, monkeypatch):
    import voice_service.bootstrap as bootstrap

    model = tmp_path / "en_GB-cori-high.onnx"
    config = tmp_path / "en_GB-cori-high.onnx.json"
    model.write_bytes(b"existing-cori")
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "EXPECTED_MODEL_SHA256", hashlib.sha256(model.read_bytes()).hexdigest())

    def forbidden_downloader(url, destination):
        raise AssertionError("verified persistent assets must not be downloaded again")

    resolved_model, resolved_config = bootstrap.ensure_cori_model(tmp_path, downloader=forbidden_downloader)

    assert resolved_model == model
    assert resolved_config == config


def test_bootstrap_fails_closed_on_bad_downloaded_digest(tmp_path, monkeypatch):
    import voice_service.bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "EXPECTED_MODEL_SHA256", hashlib.sha256(b"expected").hexdigest())

    def downloader(url, destination):
        if destination.name.endswith(".onnx"):
            destination.write_bytes(b"tampered")
        else:
            destination.write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="SHA-256"):
        bootstrap.ensure_cori_model(tmp_path, downloader=downloader)
