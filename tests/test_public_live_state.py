from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_public_live_state_is_available_without_oauth(monkeypatch):
    monkeypatch.setattr(
        main,
        "production_acceptance_snapshot",
        lambda: {
            "production_accepted": True,
            "source_commit_sha": "a" * 40,
            "release_version": "3.2.1",
            "hardening_profile": "SIOS-V3.2-FAILSAFE-1",
        },
    )

    response = client.get("/public/live-state")

    assert response.status_code == 200
    body = response.json()
    assert body["access_mode"] == "public_read_only"
    assert body["production"]["production_accepted"] is True
    assert body["agents"]["madhouse"]["can_pass"] is False
    assert body["agents"]["epistemic"]["can_pass"] is False
    assert body["authority"]["promotion_authority"] == "NONE"


def test_public_live_state_does_not_require_authorization_header():
    response = client.get("/public/live-state")

    assert response.status_code != 401
    assert response.status_code != 403
