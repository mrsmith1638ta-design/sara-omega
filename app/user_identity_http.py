from __future__ import annotations

import base64
import binascii
import hmac
import html
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .memory import MemoryKeyError
from .user_identity import (
    EnrollmentRejected,
    IdentityStoreError,
    OAuthConfigurationError,
    OAuthRejected,
    PasswordPolicyRejected,
    UserIdentityStore,
)

router = APIRouter()

_NO_STORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _store() -> UserIdentityStore:
    try:
        store = UserIdentityStore.from_env(required=True)
    except (MemoryKeyError, IdentityStoreError) as exc:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable") from exc
    if store is None:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable")
    return store


def _bearer_token(request: Request) -> str:
    value = request.headers.get("Authorization", "")
    if not value.startswith("Bearer "):
        return ""
    return value[7:]


def _require_owner(request: Request) -> None:
    owner = os.getenv("OWNER_TOKEN", "")
    action = os.getenv("GPT_ACTION_TOKEN", "")
    tester = os.getenv("TEST_TOKEN", "")
    supplied = _bearer_token(request)
    # A credential overlap is unsafe because the caller's authority would be ambiguous.
    if not owner or (action and hmac.compare_digest(owner, action)) or (tester and hmac.compare_digest(owner, tester)):
        raise HTTPException(status_code=503, detail="Owner identity configuration unavailable")
    if not supplied or not hmac.compare_digest(supplied, owner):
        raise HTTPException(status_code=403, detail="Owner only")


def _require_enrollment_bootstrap(request: Request) -> None:
    bootstrap = os.getenv("SARA_ENROLLMENT_BOOTSTRAP_TOKEN", "").strip()
    if not bootstrap:
        # Hide the temporary bootstrap surface completely when it is not enabled.
        raise HTTPException(status_code=404, detail="Not Found")
    if len(bootstrap) < 32:
        raise HTTPException(status_code=503, detail="Enrollment bootstrap configuration unavailable")

    owner = os.getenv("OWNER_TOKEN", "")
    action = os.getenv("GPT_ACTION_TOKEN", "")
    tester = os.getenv("TEST_TOKEN", "")
    if any(
        configured and hmac.compare_digest(bootstrap, configured)
        for configured in (owner, action, tester)
    ):
        raise HTTPException(status_code=503, detail="Enrollment bootstrap configuration unavailable")

    supplied = _bearer_token(request)
    if not supplied or not hmac.compare_digest(supplied, bootstrap):
        raise HTTPException(status_code=403, detail="Enrollment bootstrap denied")


def _public_base_url(request: Request) -> str:
    configured = os.getenv("SARA_PUBLIC_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    # Development fallback only. Production is expected to pin SARA_PUBLIC_BASE_URL.
    return str(request.base_url).rstrip("/")


def _page(title: str, body: str, *, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:620px;margin:48px auto;padding:0 20px;}"
        "label{display:block;margin:14px 0 5px;}input{box-sizing:border-box;width:100%;padding:10px;}"
        "button{margin-top:20px;padding:10px 18px;} .error{font-weight:600;} .id{font-size:1.2rem;font-weight:700;}"
        "</style></head><body>"
        f"{body}</body></html>",
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _enrollment_form(token: str, *, error: str = "", status_code: int = 200) -> HTMLResponse:
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    safe_token = html.escape(token, quote=True)
    return _page(
        "Create your SARA account",
        "<h1>Welcome to SARA-OMEGA</h1>"
        "<p>Create your personal SARA account. Your enrollment ID is supplied by the SARA owner.</p>"
        f"{error_html}"
        f'<form method="post" action="/enroll/{safe_token}">'
        '<label for="enrollment_id">Enrollment ID</label>'
        '<input id="enrollment_id" name="enrollment_id" required autocomplete="username">'
        '<label for="password">Create Password</label>'
        '<input id="password" name="password" type="password" required autocomplete="new-password">'
        '<label for="password_confirm">Confirm Password</label>'
        '<input id="password_confirm" name="password_confirm" type="password" required autocomplete="new-password">'
        '<button type="submit">Create My SARA Account</button></form>',
        status_code=status_code,
    )


def _oauth_login_form(
    *,
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str,
    state: str,
    error: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    hidden = "".join(
        f'<input type="hidden" name="{html.escape(key, quote=True)}" value="{html.escape(value, quote=True)}">'
        for key, value in (
            ("client_id", client_id),
            ("redirect_uri", redirect_uri),
            ("response_type", response_type),
            ("scope", scope),
            ("state", state),
        )
    )
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return _page(
        "Sign in to SARA",
        "<h1>Sign in to SARA-OMEGA</h1>"
        "<p>Use the permanent SARA user ID you received during enrollment.</p>"
        f"{error_html}"
        '<form method="post" action="/oauth/authorize">'
        f"{hidden}"
        '<label for="public_user_id">SARA User ID</label>'
        '<input id="public_user_id" name="public_user_id" required autocomplete="username">'
        '<label for="password">Password</label>'
        '<input id="password" name="password" type="password" required autocomplete="current-password">'
        '<button type="submit">Sign in to SARA</button></form>',
        status_code=status_code,
    )


def _redirect_with_code(redirect_uri: str, *, code: str, state: str) -> str:
    parsed = urlsplit(redirect_uri)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    query.append(("code", code))
    if state:
        query.append(("state", state))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _client_credentials(request: Request, form: dict[str, str]) -> tuple[str, str]:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Basic "):
        try:
            decoded = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
            client_id, client_secret = decoded.split(":", 1)
            return client_id, client_secret
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail="Invalid OAuth client credentials") from exc
    return form.get("client_id", ""), form.get("client_secret", "")


@router.post("/admin/enrollment/invitations")
async def create_enrollment_invitation(request: Request):
    _require_owner(request)
    store = _store()
    try:
        invitation = store.create_invitation(base_url=_public_base_url(request))
    except IdentityStoreError as exc:
        raise HTTPException(status_code=503, detail="Unable to create enrollment invitation") from exc
    return {
        "enrollment_id": invitation.enrollment_id,
        "enrollment_url": invitation.enrollment_url,
        "expires_at": invitation.expires_at,
    }


@router.post("/admin/enrollment/bootstrap")
async def create_bootstrap_enrollment_invitation(request: Request):
    _require_enrollment_bootstrap(request)
    store = _store()
    try:
        invitation = store.create_invitation(base_url=_public_base_url(request))
    except IdentityStoreError as exc:
        raise HTTPException(status_code=503, detail="Unable to create enrollment invitation") from exc
    return JSONResponse(
        {
            "enrollment_id": invitation.enrollment_id,
            "enrollment_url": invitation.enrollment_url,
            "expires_at": invitation.expires_at,
        },
        headers=_NO_STORE_HEADERS,
    )


@router.get("/enroll/{invite_token}")
async def enrollment_page(invite_token: str):
    if not invite_token or len(invite_token) > 256:
        raise HTTPException(status_code=404, detail="Invitation unavailable")
    return _enrollment_form(invite_token)


@router.post("/enroll/{invite_token}")
async def enroll_user(invite_token: str, request: Request):
    form_data = await request.form()
    enrollment_id = str(form_data.get("enrollment_id", ""))
    password = str(form_data.get("password", ""))
    password_confirm = str(form_data.get("password_confirm", ""))
    store = _store()
    try:
        account = store.enroll(
            invite_token=invite_token,
            enrollment_id=enrollment_id,
            password=password,
            password_confirm=password_confirm,
        )
    except PasswordPolicyRejected as exc:
        message = "Passwords do not match." if str(exc) == "password_confirmation_mismatch" else (
            "Password must be 12-128 characters and use at least three character classes."
        )
        return _enrollment_form(invite_token, error=message, status_code=400)
    except EnrollmentRejected:
        return _enrollment_form(invite_token, error="Enrollment could not be completed.", status_code=400)
    except IdentityStoreError as exc:
        raise HTTPException(status_code=503, detail="SARA identity persistence unavailable") from exc

    gpt_url = os.getenv("SARA_GPT_URL", "").strip()
    gpt_link = (
        f'<p><a href="{html.escape(gpt_url, quote=True)}">Open SARA-OMEGA</a></p>' if gpt_url else ""
    )
    return _page(
        "SARA account created",
        "<h1>SARA account created</h1>"
        "<p>Your permanent SARA User ID is:</p>"
        f'<p class="id">{html.escape(account.public_user_id)}</p>'
        "<p>Keep this user ID. Your password is not displayed or recoverable.</p>"
        f"{gpt_link}",
    )


@router.get("/oauth/authorize")
async def oauth_authorize_page(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "",
    state: str = "",
):
    store = _store()
    try:
        canonical_scope = store.validate_authorization_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            scope=scope,
        )
    except (OAuthRejected, OAuthConfigurationError) as exc:
        raise HTTPException(status_code=400, detail="OAuth authorization request rejected") from exc
    return _oauth_login_form(
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type=response_type,
        scope=canonical_scope,
        state=state,
    )


@router.post("/oauth/authorize")
async def oauth_authorize_login(request: Request):
    raw = await request.form()
    form = {str(key): str(value) for key, value in raw.items()}
    store = _store()
    client_id = form.get("client_id", "")
    redirect_uri = form.get("redirect_uri", "")
    response_type = form.get("response_type", "code")
    scope = form.get("scope", "")
    state = form.get("state", "")
    try:
        canonical_scope = store.validate_authorization_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            scope=scope,
        )
    except (OAuthRejected, OAuthConfigurationError) as exc:
        raise HTTPException(status_code=400, detail="OAuth authorization request rejected") from exc
    try:
        account = store.authenticate_for_oauth(form.get("public_user_id", ""), form.get("password", ""))
    except OAuthRejected as exc:
        message = "Account temporarily locked." if str(exc) == "authentication_locked" else "Invalid SARA user ID or password."
        return _oauth_login_form(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            scope=canonical_scope,
            state=state,
            error=message,
            status_code=401,
        )
    code = store.issue_authorization_code(
        user_uuid=account.user_uuid,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=canonical_scope,
    )
    return RedirectResponse(
        _redirect_with_code(redirect_uri, code=code, state=state),
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/oauth/token")
async def oauth_token(request: Request):
    raw = await request.form()
    form = {str(key): str(value) for key, value in raw.items()}
    client_id, client_secret = _client_credentials(request, form)
    grant_type = form.get("grant_type", "")
    store = _store()
    try:
        if grant_type == "authorization_code":
            bundle = store.exchange_authorization_code(
                code=form.get("code", ""),
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=form.get("redirect_uri", ""),
            )
        elif grant_type == "refresh_token":
            bundle = store.refresh_access_token(
                refresh_token=form.get("refresh_token", ""),
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            raise OAuthRejected("oauth_grant_type_rejected")
    except OAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="SARA OAuth is not configured") from exc
    except OAuthRejected:
        return JSONResponse(
            {"error": "invalid_grant"},
            status_code=400,
            headers=_NO_STORE_HEADERS,
        )
    return JSONResponse(
        {
            "access_token": bundle.access_token,
            "refresh_token": bundle.refresh_token,
            "token_type": bundle.token_type,
            "expires_in": bundle.expires_in,
            "scope": bundle.scope,
        },
        headers=_NO_STORE_HEADERS,
    )


@router.post("/oauth/revoke")
async def oauth_revoke(request: Request):
    raw = await request.form()
    form = {str(key): str(value) for key, value in raw.items()}
    client_id, client_secret = _client_credentials(request, form)
    try:
        _store().revoke_token(
            token=form.get("token", ""),
            client_id=client_id,
            client_secret=client_secret,
        )
    except OAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="SARA OAuth is not configured") from exc
    except OAuthRejected:
        # OAuth revocation is deliberately non-enumerating.
        pass
    return Response(status_code=200, headers=_NO_STORE_HEADERS)


@router.get("/oauth/status")
async def oauth_status():
    return _store().oauth_status()
