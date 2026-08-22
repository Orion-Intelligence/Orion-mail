from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status

from orion.constants.constant import CONSTANTS


class orion_identity_client:
    __instance = None

    @staticmethod
    def get_instance():
        if orion_identity_client.__instance is None:
            orion_identity_client()
        return orion_identity_client.__instance

    def __init__(self):
        if orion_identity_client.__instance is not None:
            raise Exception("This class is a singleton!")
        orion_identity_client.__instance = self

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "X-Orion-Mail-Client-Secret": CONSTANTS.S_ORION_MAIL_SSO_CLIENT_SECRET,
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{CONSTANTS.S_ORION_INTELLIGENCE_INTERNAL_URL}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=CONSTANTS.S_ORION_SSO_TIMEOUT_SECONDS,
                trust_env=False,
            ) as client:
                response = await client.post(url, headers=self._headers(), json=payload)
        except httpx.RequestError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orion Intelligence authentication is unavailable",
            ) from error

        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Orion Intelligence session",
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orion Intelligence authentication is unavailable",
            )

        try:
            return response.json()
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Invalid response from Orion Intelligence",
            ) from error

    async def exchange(self, *, code: str, redirect_uri: str) -> dict[str, Any]:
        return await self._post(
            "/api/sso/mail/exchange",
            {"code": code, "redirect_uri": redirect_uri},
        )

    async def verify(self, session_token: str) -> dict[str, Any]:
        return await self._post(
            "/api/sso/mail/session", {"session_token": session_token}
        )

    async def revoke(self, session_token: str) -> None:
        await self._post(
            "/api/sso/mail/revoke", {"session_token": session_token}
        )
