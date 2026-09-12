import re
import os
import secrets

from fastapi import HTTPException, Request, status

from configs.auth_cookie import session_token_from_request
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.services.orion_identity_manager.orion_identity_client import (orion_identity_client,)
from orion.services.orion_identity_manager.orion_identity_manager import (orion_identity_manager,)
from orion.services.mongo_manager.mongo_controller import mongo_controller

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-requested-with"
CSRF_HEADER_VALUE = "XMLHttpRequest"
INGEST_AUTH_HEADER = "x-incoming-mail-token"
TEST_SESSION_COOKIE = "orion_mail_test_session"



LOCAL_ORIGIN_PATTERN = re.compile(r"^http://(?:localhost|127\.0\.0\.1)(?::\d+)?$")


def allowed_origins() -> set[str]:
    return {
        f"https://{CONSTANTS.S_MAIL_DOMAIN}",
        *CONSTANTS.S_CORS_ALLOWED_ORIGINS,
        *CONSTANTS.S_ORION_MAIL_PUBLIC_URLS,
    }


def is_origin_allowed(origin: str) -> bool:
    return origin in allowed_origins() or (not CONSTANTS.S_COOKIE_SECURE and bool(LOCAL_ORIGIN_PATTERN.match(origin)))


def enforce_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF protection header")
    origin = request.headers.get("origin")
    if origin and not is_origin_allowed(origin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")


async def get_current_user(request: Request) -> db_user_model:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
    )

    # Cypress/test-only authentication.
    if os.getenv("ORION_TESTING", "false").lower() == "true":
        test_username = request.cookies.get(TEST_SESSION_COOKIE)

        if test_username in {"test1", "test2", "test3", "test4"}:
            enforce_csrf(request)

            test_user = await mongo_controller.get_instance().get_engine().find_one(
                db_user_model,
                db_user_model.username == test_username,
            )

            if test_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Test user not found",
                )

            return test_user

    # Normal Orion Intelligence authentication.
    token = session_token_from_request(request)

    if not token:
        raise credentials_error

    enforce_csrf(request)

    identity = await orion_identity_client.get_instance().verify(token)

    return await orion_identity_manager.get_instance().link_identity(identity)


def require_incoming_mail_token(request: Request) -> None:
    expected = CONSTANTS.S_INCOMING_MAIL_TOKEN
    provided = request.headers.get(INGEST_AUTH_HEADER, "")
    if not expected or not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
