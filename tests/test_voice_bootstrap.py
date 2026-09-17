import hashlib

import pytest


def test_runtime_bootstrap_downloads_missing_cori_assets(tmp_path, monkeypatch):
    import voice_service.bootstrap as bootstrap

    model_bytes = b"verified-cori-model"
    config_bytes = b'{"audio":{"sample_rate":22050}}'
    monkeypatch.setattr(bootstrap, "EXPECTED_MODEL_SHA256", hashlib.sha256(model_bytes).hexdigest())
    calls = []

    def fake_download(url, destination):
        calls.append((url, str(destination)))
        if str(destination).endswith(".onnx.json"):
            destination.write_bytes(config_bytes)
        else:
            destination.write_bytes(model_bytes)

    model_path = bootstrap.ensure_cori_model(tmp_path, downloader=fake_download)

    assert model_path == tmp_path / "en_GB-cori-high.onnx"
    assert model_path.read_bytes() == model_bytes
    assert (tmp_path / "en_GB-cori-high.onnx.json").read_bytes() == config_bytes
    assert len(calls) == 2


def test_runtime_bootstrap_rejects_tampered_existing_model(tmp_path, monkeypatch):
    import voice_service.bootstrap as bootstrap

    expected = b"approved-model"
    monkeypatch.setattr(bootstrap, "EXPECTED_MODEL_SHA256", hashlib.sha256(expected).hexdigest())
    model = tmp_path / "en_GB-cori-high.onnx"
    model.write_bytes(b"tampered")
    (tmp_path / "en_GB-cori-high.onnx.json").write_text("{}", encoding="utf-8")

    def must_not_download(url, destination):
        raise AssertionError("tampered existing model must fail closed, not be replaced silently")

    with pytest.raises(RuntimeError, match="SHA-256"):
        bootstrap.ensure_cori_model(tmp_path, downloader=must_not_download)


def test_runtime_bootstrap_reuses_verified_persistent_assets(tmp_path, monkeypatch):
    import voice_service.bootstrap as bootstrap

    model_bytes = b"approved-model"
    monkeypatch.setattr(bootstrap, "EXPECTED_MODEL_SHA256", hashlib.sha256(model_bytes).hexdigest())
    model = tmp_path / "en_GB-cori-high.onnx"
    config = tmp_path / "en_GB-cori-high.onnx.json"
    model.write_bytes(model_bytes)
    config.write_text("{}", encoding="utf-8")

    def must_not_download(url, destination):
        raise AssertionError("verified persistent assets should be reused")

    assert bootstrap.ensure_cori_model(tmp_path, downloader=must_not_download) == model
