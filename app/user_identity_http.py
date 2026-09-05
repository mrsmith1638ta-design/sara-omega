from __future__ import annotations

import base64
import binascii
import hmac
import html
import logging
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .memory import MemoryKeyError
from .oauth_identity import OAuthUserIdentityStore
from .user_identity import (
    EnrollmentRejected,
    IdentityStoreError,
    OAuthConfigurationError,
    OAuthRejected,
    PasswordPolicyRejected,
)

router = APIRouter()
logger = logging.getLogger("sara.oauth")

_NO_STORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _store() -> OAuthUserIdentityStore:
    try:
        store = OAuthUserIdentityStore.from_env(required=True)
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
    if not owner or (action and hmac.compare_digest(owner, action)) or (tester and hmac.compare_digest(owner, tester)):
        raise HTTPException(status_code=503, detail="Owner identity configuration unavailable")
    if not supplied or not hmac.compare_digest(supplied, owner):
        raise HTTPException(status_code=403, detail="Owner only")


def _require_enrollment_bootstrap(request: Request) -> None:
    bootstrap = os.getenv("SARA_ENROLLMENT_BOOTSTRAP_TOKEN", "").strip()
    if not bootstrap:
        raise HTTPException(status_code=404, detail="Not Found")
    if len(bootstrap) < 32:
        raise HTTPException(status_code=503, detail="Enrollment bootstrap configuration unavailable")

    owner = os.getenv("OWNER_TOKEN", "")
    action = os.getenv("GPT_ACTION_TOKEN", "")
    tester = os.getenv("TEST_TOKEN", "")
    if any(configured and hmac.compare_digest(bootstrap, configured) for configured in (owner, action, tester)):
        raise HTTPException(status_code=503, detail="Enrollment bootstrap configuration unavailable")

    supplied = _bearer_token(request)
    if not supplied or not hmac.compare_digest(supplied, bootstrap):
        raise HTTPException(status_code=403, detail="Enrollment bootstrap denied")


def _public_base_url(request: Request) -> str:
    configured = os.getenv("SARA_PUBLIC_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def _page(title: str, body: str, *, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:620px;margin:48px auto;padding:0 20px;}"
        "label{display:block;margin:14px 0 5px;}input{box-sizing:border-box;width:100%;padding:10px;}"
        "button{margin:20px 8px 0 0;padding:10px 18px;} .error{font-weight:600;} .id{font-size:1.2rem;font-weight:700;}"
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
    code_challenge: str = "",
    code_challenge_method: str = "",
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
            ("code_challenge", code_challenge),
            ("code_challenge_method", code_challenge_method),
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


def _oauth_consent_form(*, authorization_session: str, scope: str) -> HTMLResponse:
    safe_session = html.escape(authorization_session, quote=True)
    safe_scope = html.escape(scope)
    return _page(
        "Authorize SARA-OMEGA",
        "<h1>Authorize SARA-OMEGA</h1>"
        f"<p>The connected GPT is requesting these SARA permissions: <strong>{safe_scope}</strong>.</p>"
        '<p>Approve only if you want this GPT to act with these permissions.</p>'
        '<form method="post" action="/oauth/consent">'
        f'<input type="hidden" name="authorization_session" value="{safe_session}">'
        '<button type="submit" name="decision" value="approve">Approve</button>'
        '<button type="submit" name="decision" value="deny">Deny</button>'
        "</form>",
    )


def _redirect_with_code(redirect_uri: str, *, code: str, state: str) -> str:
    parsed = urlsplit(redirect_uri)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    query.extend((("code", code), ("state", state)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _redirect_with_error(redirect_uri: str, *, error: str, state: str) -> str:
    parsed = urlsplit(redirect_uri)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    query.extend((("error", error), ("state", state)))
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


def _rejection_reason(exc: BaseException) -> str:
    value = str(exc)
    return {
        "oauth_client_rejected": "unknown_client",
        "oauth_redirect_uri_rejected": "redirect_uri_mismatch",
        "oauth_response_type_rejected": "unsupported_response_type",
        "oauth_scope_rejected": "scope_not_allowed",
        "invalid_pkce_method": "invalid_pkce_method",
        "invalid_pkce_challenge": "invalid_pkce_method",
        "oauth_configuration_required": "server_configuration_error",
    }.get(value, "server_configuration_error")


def _log_authorize_rejection(
    reason: str,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str,
    response_type: str,
    code_challenge: str,
    code_challenge_method: str,
) -> None:
    safe_response_type = response_type if response_type in {"", "code"} else "other"
    safe_pkce_method = code_challenge_method if code_challenge_method in {"", "S256"} else "other"
    logger.warning(
        "oauth_authorize_rejected reason=%s client_id_state=%s redirect_uri_state=%s state_present=%s "
        "scope_state=%s response_type=%s pkce_present=%s pkce_method=%s",
        reason,
        "present" if client_id else "missing",
        "present" if redirect_uri else "missing",
        bool(state),
        "present" if scope else "default",
        safe_response_type,
        bool(code_challenge),
        safe_pkce_method,
    )


def _validate_authorization_inputs(
    store: OAuthUserIdentityStore,
    *,
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str,
) -> str:
    if not response_type:
        reason = "missing_response_type"
    elif response_type != "code":
        reason = "unsupported_response_type"
    elif not client_id:
        reason = "missing_client_id"
    elif not redirect_uri:
        reason = "missing_redirect_uri"
    elif not state or not state.strip():
        reason = "missing_state"
    else:
        try:
            store.validate_pkce_parameters(code_challenge, code_challenge_method)
            return store.validate_authorization_request(
                client_id=client_id,
                redirect_uri=redirect_uri,
                response_type=response_type,
                scope=scope,
            )
        except (OAuthRejected, OAuthConfigurationError) as exc:
            reason = _rejection_reason(exc)
    _log_authorize_rejection(
        reason,
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        scope=scope,
        response_type=response_type,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    raise HTTPException(status_code=400, detail="OAuth authorization request rejected")


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
    gpt_link = f'<p><a href="{html.escape(gpt_url, quote=True)}">Open SARA-OMEGA</a></p>' if gpt_url else ""
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
    client_id: str = "",
    redirect_uri: str = "",
    response_type: str = "",
    scope: str = "",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
):
    store = _store()
    canonical_scope = _validate_authorization_inputs(
        store,
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type=response_type,
        scope=scope,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    return _oauth_login_form(
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type=response_type,
        scope=canonical_scope,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )


@router.post("/oauth/authorize")
async def oauth_authorize_login(request: Request):
    raw = await request.form()
    form = {str(key): str(value) for key, value in raw.items()}
    store = _store()
    client_id = form.get("client_id", "")
    redirect_uri = form.get("redirect_uri", "")
    response_type = form.get("response_type", "")
    scope = form.get("scope", "")
    state = form.get("state", "")
    code_challenge = form.get("code_challenge", "")
    code_challenge_method = form.get("code_challenge_method", "")
    canonical_scope = _validate_authorization_inputs(
        store,
        client_id=client_id,
        redirect_uri=redirect_uri,
        response_type=response_type,
        scope=scope,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
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
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            error=message,
            status_code=401,
        )
    try:
        authorization_session = store.create_authorization_session(
            user_uuid=account.user_uuid,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=canonical_scope,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
    except (OAuthRejected, IdentityStoreError) as exc:
        raise HTTPException(status_code=400, detail="OAuth authorization request rejected") from exc
    return _oauth_consent_form(authorization_session=authorization_session, scope=canonical_scope)


@router.post("/oauth/consent")
async def oauth_consent(request: Request):
    raw = await request.form()
    form = {str(key): str(value) for key, value in raw.items()}
    try:
        result = _store().complete_authorization_session(
            form.get("authorization_session", ""),
            form.get("decision", ""),
        )
    except (OAuthRejected, IdentityStoreError) as exc:
        raise HTTPException(status_code=400, detail="OAuth consent request rejected") from exc
    if not result.approved:
        return RedirectResponse(
            _redirect_with_error(result.redirect_uri, error="access_denied", state=result.state),
            status_code=303,
            headers={"Cache-Control": "no-store"},
        )
    return RedirectResponse(
        _redirect_with_code(result.redirect_uri, code=result.code, state=result.state),
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
                code_verifier=form.get("code_verifier", ""),
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
        return JSONResponse({"error": "invalid_grant"}, status_code=400, headers=_NO_STORE_HEADERS)
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
        pass
    return Response(status_code=200, headers=_NO_STORE_HEADERS)


@router.get("/oauth/status")
async def oauth_status():
    return _store().oauth_status()
