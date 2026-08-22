from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from odmantic.exceptions import DuplicateKeyError

from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class orion_identity_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if orion_identity_manager.__instance is None:
            orion_identity_manager()
        return orion_identity_manager.__instance

    def __init__(self):
        if orion_identity_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        orion_identity_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def _normalized_identity(identity: dict[str, Any]) -> dict[str, str]:
        orion_user_id = str(identity.get("user_id") or "").strip()
        tenant_id = str(identity.get("tenant_id") or "").strip()
        username = str(identity.get("username") or "").strip()
        email = str(identity.get("email") or "").strip().lower()
        if not orion_user_id or not tenant_id or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incomplete Orion Intelligence identity",
            )
        return {
            "orion_user_id": orion_user_id,
            "orion_tenant_id": tenant_id,
            "username": username,
            "email": email or username.lower(),
            "full_name": str(identity.get("full_name") or username).strip()
            or username,
        }

    async def link_identity(self, identity: dict[str, Any]) -> db_user_model:
        profile = self._normalized_identity(identity)
        user = await self._engine.find_one(
            db_user_model,
            db_user_model.orion_user_id == profile["orion_user_id"],
        )

        if user is None:
            email_match = await self._engine.find_one(
                db_user_model, db_user_model.email == profile["email"]
            )
            if email_match is not None and email_match.orion_user_id not in (
                None,
                "",
                profile["orion_user_id"],
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This Orion account conflicts with an existing Mail profile",
                )
            user = email_match or db_user_model(
                full_name=profile["full_name"],
                email=profile["email"],
            )

        user.full_name = profile["full_name"]
        user.email = profile["email"]
        user.username = profile["username"]
        user.orion_user_id = profile["orion_user_id"]
        user.orion_tenant_id = profile["orion_tenant_id"]
        user.updated_at = datetime.now(UTC)

        try:
            saved_user = await self._engine.save(user)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Orion account conflicts with an existing Mail profile",
            ) from error

        await key_manager.get_instance().get_or_create_user_keys(str(saved_user.id))
        return saved_user
