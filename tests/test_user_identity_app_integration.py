from __future__ import annotations


def test_production_app_exposes_user_identity_routes():
    from app.enterprise_runtime import router as enterprise_router
    import main

    expected = {
        "/admin/enrollment/invitations",
        "/enroll/{invite_token}",
        "/oauth/authorize",
        "/oauth/token",
        "/oauth/revoke",
        "/oauth/status",
    }
    enterprise_paths = {getattr(route, "path", "") for route in enterprise_router.routes}
    app_paths = {getattr(route, "path", "") for route in main.app.routes}
    assert expected.issubset(enterprise_paths)
    assert expected.issubset(app_paths)
