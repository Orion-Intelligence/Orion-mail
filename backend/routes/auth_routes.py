from __future__ import annotations

import contextlib
import re
import secrets
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from configs.app_dependency import enforce_csrf, get_current_user
from configs.auth_cookie import (
    clear_session_cookie,
    clear_sso_cookies,
    session_token_from_request,
    set_session_cookie,
    set_sso_cookies,
    sso_redirect_from_request,
    sso_return_to_from_request,
    sso_state_from_request,
)
from orion.api.interactive.preference_manager.models.preference_param_model import UserPreferencesRequest
from orion.api.interactive.preference_manager.preference_manager import preference_manager
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.services.orion_identity_manager.orion_identity_client import (
    orion_identity_client,
)
from orion.services.orion_identity_manager.orion_identity_manager import (
    orion_identity_manager,
)

auth_routes = APIRouter(prefix="/auth", tags=["Authentication"])


SAFE_RETURN_TO = re.compile(r"^/(?![/\\])[A-Za-z0-9._~\-/]*(?:\?[A-Za-z0-9._~\-/&=%+]*)?$")


def safe_return_to(value: str | None) -> str:
    candidate = (value or "/inbox").strip()
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return "/inbox"
    destination = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return destination if SAFE_RETURN_TO.match(destination) else "/inbox"


def allowed_mail_origin(value: str | None) -> str:
    candidate = (value or "").strip().rstrip("/")
    if not candidate:
        candidate = CONSTANTS.S_ORION_MAIL_PUBLIC_URLS[0]
    parsed = urlsplit(candidate)
    if (
        candidate not in CONSTANTS.S_ORION_MAIL_PUBLIC_URLS
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unrecognized Orion Mail origin",
        )
    return candidate


async def mailbox_for_user(user: db_user_model) -> db_mailbox_model | None:
    return await mongo_controller.get_instance().get_engine().find_one(
        db_mailbox_model, db_mailbox_model.user_id == user.id
    )


def current_user_response(user: db_user_model, mailbox: db_mailbox_model | None) -> dict:
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "username": user.username,
        "mailbox_configured": mailbox is not None,
        "mailbox_address": mailbox.mailbox_address if mailbox else None,
        "mail_domain": CONSTANTS.S_MAIL_DOMAIN,
        "orion_account_url": f"{CONSTANTS.S_ORION_INTELLIGENCE_PUBLIC_URL}/dashboard/profile/account",
        "preferences": preference_manager.serialize_preferences(user),
    }


@auth_routes.get("/login")
async def begin_orion_login(origin: str | None = Query(default=None), return_to: str | None = Query(default=None)):
    mail_origin = allowed_mail_origin(origin)
    redirect_uri = f"{mail_origin}/auth/callback"
    state = secrets.token_urlsafe(32)
    destination = safe_return_to(return_to)
    authorize_url = (
        f"{CONSTANTS.S_ORION_INTELLIGENCE_PUBLIC_URL}/api/sso/mail/authorize?"
        + urlencode({"redirect_uri": redirect_uri, "state": state})
    )
    response = RedirectResponse(authorize_url, status_code=status.HTTP_302_FOUND)
    set_sso_cookies(
        response,
        state=state,
        redirect_uri=redirect_uri,
        return_to=destination,
    )
    return response


@auth_routes.get("/callback")
async def complete_orion_login(request: Request, code: str, state: str):
    expected_state = sso_state_from_request(request)
    redirect_uri = sso_redirect_from_request(request)
    if (
        not expected_state
        or not state
        or not secrets.compare_digest(expected_state, state)
        or not redirect_uri
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired sign-in request",
        )

    result = await orion_identity_client.get_instance().exchange(
        code=code, redirect_uri=redirect_uri
    )
    session_token = str(result.get("session_token") or "")
    identity = result.get("identity")
    if not session_token or not isinstance(identity, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invalid response from Orion Intelligence",
        )

    user = await orion_identity_manager.get_instance().link_identity(identity)
    mailbox = await mailbox_for_user(user)
    return_to = safe_return_to(sso_return_to_from_request(request))
    destination = return_to if mailbox else "/configure-email"
    response = RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    expires_in = min(
        max(int(result.get("expires_in") or 0), 1),
        CONSTANTS.S_ORION_MAIL_SESSION_MAX_AGE_SECONDS,
    )
    set_session_cookie(response, session_token, max_age=expires_in)
    clear_sso_cookies(response)
    return response


@auth_routes.get("/me")
async def get_me(current_user: db_user_model = Depends(get_current_user)):
    return current_user_response(current_user, await mailbox_for_user(current_user))


@auth_routes.put("/me/preferences")
async def update_my_preferences(preference_data: UserPreferencesRequest, current_user: db_user_model = Depends(get_current_user)):
    return await preference_manager.get_instance().update_preferences(current_user=current_user, preferences=preference_data.model_dump())


@auth_routes.post("/logout")
async def logout(request: Request, response: Response):
    enforce_csrf(request)
    session_token = session_token_from_request(request)
    if session_token:
        with contextlib.suppress(HTTPException):
            await orion_identity_client.get_instance().revoke(session_token)

    clear_session_cookie(response)
    clear_sso_cookies(response)
    return {
        "message": "Logged out successfully",
        "redirect_url": f"{CONSTANTS.S_ORION_INTELLIGENCE_PUBLIC_URL}/login",
    }
