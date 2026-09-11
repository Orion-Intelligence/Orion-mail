import os

from fastapi import APIRouter, HTTPException, Response, status


test_auth_routes = APIRouter(prefix="/test", tags=["Testing"])


def testing_enabled() -> bool:
    return os.getenv("ORION_TESTING", "false").lower() == "true"


@test_auth_routes.post("/login")
async def test_login(response: Response):
    if not testing_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    response.set_cookie(
        key="orion_mail_test_session",
        value="test1",
        httponly=True,
        samesite="lax",
        secure=False,
    )

    return {
        "message": "Test authentication established",
        "username": "test1",
    }