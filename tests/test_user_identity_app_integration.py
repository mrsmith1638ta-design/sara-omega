from __future__ import annotations

from fastapi.testclient import TestClient


def test_production_app_exposes_user_identity_routes():
    import main

    client = TestClient(main.app)

    # Test the actual ASGI routing contract instead of assuming FastAPI's
    # internal route table must flatten nested APIRouters.
    enrollment = client.get("/enroll/route-probe-token")
    assert enrollment.status_code == 200
    assert "Create My SARA Account" in enrollment.text

    oauth_authorize = client.get("/oauth/authorize")
    assert oauth_authorize.status_code in {400, 422}
    assert oauth_authorize.status_code != 404

    oauth_status = client.get("/oauth/status")
    assert oauth_status.status_code in {200, 503}
    assert oauth_status.status_code != 404

    oauth_token = client.post("/oauth/token", data={})
    assert oauth_token.status_code in {400, 503}
    assert oauth_token.status_code != 404

    oauth_revoke = client.post("/oauth/revoke", data={})
    assert oauth_revoke.status_code in {200, 503}
    assert oauth_revoke.status_code != 404

    invitation = client.post("/admin/enrollment/invitations")
    assert invitation.status_code in {403, 503}
    assert invitation.status_code != 404

    user_gateway = client.post("/gpt/user/gateway", json={"operation": "memory_status"})
    assert user_gateway.status_code == 401
