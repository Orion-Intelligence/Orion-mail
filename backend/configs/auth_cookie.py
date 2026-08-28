import re
from urllib.parse import quote, unquote

from fastapi import Request, Response

from orion.constants.constant import CONSTANTS

SESSION_COOKIE = "orion_mail_session"
SSO_STATE_COOKIE = "orion_mail_sso_state"
SSO_REDIRECT_COOKIE = "orion_mail_sso_redirect"
SSO_RETURN_TO_COOKIE = "orion_mail_sso_return_to"
COOKIE_MAX_AGE = CONSTANTS.S_ORION_MAIL_SESSION_MAX_AGE_SECONDS
SSO_COOKIE_MAX_AGE = 5 * 60
SSO_CALLBACK_PATH = "/auth/callback"
SSO_RETURN_TO_FALLBACK = "/inbox"
SSO_RETURN_TO_PATTERN = re.compile(r"^/[A-Za-z0-9._~\-/]*(?:\?[A-Za-z0-9._~\-/=&%]*)?$")


def set_session_cookie(response: Response, token: str, max_age: int = COOKIE_MAX_AGE) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=max_age,
        path="/",
        secure=CONSTANTS.S_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=CONSTANTS.S_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def session_token_from_request(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def allowed_sso_redirect_uri(redirect_uri: str) -> str:
    for public_url in CONSTANTS.S_ORION_MAIL_PUBLIC_URLS:
        callback_uri = f"{public_url}{SSO_CALLBACK_PATH}"
        if redirect_uri == callback_uri:
            return callback_uri
    return f"{CONSTANTS.S_ORION_MAIL_PUBLIC_URLS[0]}{SSO_CALLBACK_PATH}"


def allowed_sso_return_to(return_to: str) -> str:
    if not return_to:
        return SSO_RETURN_TO_FALLBACK

    clean_value = unquote(return_to).strip()

    if clean_value.startswith("//"):
        return SSO_RETURN_TO_FALLBACK

    path = clean_value.split("?", 1)[0].split("#", 1)[0]

    if not path.startswith("/") or not re.fullmatch(r"/[A-Za-z0-9._~\-/]*", path):
        return SSO_RETURN_TO_FALLBACK

    return path


def set_sso_cookies(response: Response, *, state: str, redirect_uri: str, return_to: str) -> None:
    cookie_options = {
        "max_age": SSO_COOKIE_MAX_AGE,
        "path": "/auth",
        "secure": CONSTANTS.S_COOKIE_SECURE,
        "httponly": True,
        "samesite": "lax",
    }
    response.set_cookie(key=SSO_STATE_COOKIE, value=state, **cookie_options)
    response.set_cookie(key=SSO_REDIRECT_COOKIE, value=quote(allowed_sso_redirect_uri(redirect_uri), safe=""), **cookie_options)
    response.set_cookie(key=SSO_RETURN_TO_COOKIE, value=quote(allowed_sso_return_to(return_to), safe=""), **cookie_options)


def clear_sso_cookies(response: Response) -> None:
    for key in (SSO_STATE_COOKIE, SSO_REDIRECT_COOKIE, SSO_RETURN_TO_COOKIE):
        response.delete_cookie(
            key=key,
            path="/auth",
            secure=CONSTANTS.S_COOKIE_SECURE,
            httponly=True,
            samesite="lax",
        )


def sso_state_from_request(request: Request) -> str | None:
    return request.cookies.get(SSO_STATE_COOKIE)


def sso_redirect_from_request(request: Request) -> str | None:
    value = request.cookies.get(SSO_REDIRECT_COOKIE)
    return unquote(value) if value else None


def sso_return_to_from_request(request: Request) -> str | None:
    value = request.cookies.get(SSO_RETURN_TO_COOKIE)
    return unquote(value) if value else None
