from __future__ import annotations

import pytest

import sara_production_bootstrap as bootstrap


def test_no_start_exits_before_preflight_and_server(monkeypatch):
    monkeypatch.setenv("SARA_NO_START", "true")

    def forbidden(*args, **kwargs):
        raise AssertionError("NO-START must exit before preflight/import/server work")

    monkeypatch.setattr(bootstrap, "run_preflight", forbidden)
    monkeypatch.setattr(bootstrap.uvicorn, "run", forbidden)

    with pytest.raises(SystemExit) as exc:
        bootstrap.run()

    assert exc.value.code == 0
