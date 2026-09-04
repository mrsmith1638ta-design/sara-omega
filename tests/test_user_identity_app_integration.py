from __future__ import annotations


def test_production_app_exposes_user_identity_routes():
    import main

    paths = {getattr(route, "path", "") for route in main.app.routes}
    assert "/admin/enrollment/invitations" in paths
    assert "/enroll/{invite_token}" in paths
    assert "/oauth/authorize" in paths
    assert "/oauth/token" in paths
    assert "/oauth/revoke" in paths
    assert "/oauth/status" in paths
