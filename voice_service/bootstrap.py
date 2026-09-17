from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

MODEL_NAME = "en_GB-cori-high.onnx"
CONFIG_NAME = f"{MODEL_NAME}.json"
MODEL_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/cori/high/"
EXPECTED_MODEL_SHA256 = "470b4dd634c98f8a4850d7626ffc3dfc90774628eeef6605a6dd8f88f30a5903"
METADATA_NAME = ".sara-piper-bootstrap.json"

Downloader = Callable[[str, Path], None]


@dataclass(frozen=True)
class BootstrapResult:
    model_path: Path
    config_path: Path
    model_sha256: str
    reused_existing: bool


def _download(url: str, destination: Path) -> None:
    temp = destination.with_suffix(destination.suffix + ".tmp")
    urllib.request.urlretrieve(url, temp)
    temp.replace(destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_metadata(result: BootstrapResult) -> None:
    metadata = {
        "model_path": str(result.model_path),
        "model_sha256": result.model_sha256,
        "reused_existing_model": result.reused_existing,
    }
    destination = result.model_path.parent / METADATA_NAME
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    temp.replace(destination)


def ensure_cori_model(model_dir: Path | str, *, downloader: Downloader = _download) -> BootstrapResult:
    root = Path(model_dir)
    root.mkdir(parents=True, exist_ok=True)
    model = root / MODEL_NAME
    config = root / CONFIG_NAME

    if model.is_file() and config.is_file():
        actual = _sha256(model)
        if actual == EXPECTED_MODEL_SHA256:
            print(f"Verified persistent Cori model SHA-256: {actual}", flush=True)
            result = BootstrapResult(model, config, actual, True)
            _write_metadata(result)
            return result
        model.unlink(missing_ok=True)
        config.unlink(missing_ok=True)
        (root / METADATA_NAME).unlink(missing_ok=True)

    downloader(MODEL_BASE_URL + MODEL_NAME, model)
    downloader(MODEL_BASE_URL + CONFIG_NAME, config)

    if not model.is_file() or not config.is_file():
        raise RuntimeError("Piper Cori model bootstrap did not produce both required files")

    actual = _sha256(model)
    if actual != EXPECTED_MODEL_SHA256:
        model.unlink(missing_ok=True)
        config.unlink(missing_ok=True)
        (root / METADATA_NAME).unlink(missing_ok=True)
        raise RuntimeError(
            f"Piper Cori model SHA-256 mismatch: expected {EXPECTED_MODEL_SHA256}, got {actual}"
        )

    print(f"Downloaded and verified Cori model SHA-256: {actual}", flush=True)
    result = BootstrapResult(model, config, actual, False)
    _write_metadata(result)
    return result


def main() -> int:
    model_path = Path(os.getenv("PIPER_MODEL_PATH", "/models/en_GB-cori-high.onnx"))
    if model_path.name != MODEL_NAME:
        raise RuntimeError(f"PIPER_MODEL_PATH must end with {MODEL_NAME}")
    result = ensure_cori_model(model_path.parent)
    os.environ["PIPER_MODEL_PATH"] = str(result.model_path)
    os.environ["PIPER_MODEL_SHA256"] = result.model_sha256
    os.environ["PIPER_MODEL_REUSED_EXISTING"] = "true" if result.reused_existing else "false"
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"voice bootstrap failed: {exc}", file=sys.stderr, flush=True)
        raise
