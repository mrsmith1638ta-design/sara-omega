from __future__ import annotations

import json
from pathlib import Path


def test_railway_runtime_uses_long_running_web_launcher() -> None:
    config = json.loads(Path("railway.json").read_text(encoding="utf-8"))
    assert config["deploy"]["startCommand"] == "python sara_web.py"

    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["python", "sara_web.py"]' in dockerfile
