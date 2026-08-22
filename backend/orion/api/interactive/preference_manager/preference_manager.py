from datetime import UTC, datetime
from typing import Any

from orion.api.interactive.preference_manager.preference_enums import PREFERENCE_KEYS
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class preference_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if preference_manager.__instance is None:
            preference_manager()
        return preference_manager.__instance

    def __init__(self):
        if preference_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        preference_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def serialize_preferences(user: db_user_model) -> dict[str, Any]:
        preferences = user.preferences or {}
        return {PREFERENCE_KEYS.THEME: preferences.get(PREFERENCE_KEYS.THEME)}

    async def update_preferences(self, current_user: db_user_model, preferences: dict[str, Any]) -> dict[str, Any]:
        current_user.preferences = {**(current_user.preferences or {}), **preferences}
        current_user.updated_at = datetime.now(UTC)
        await self._engine.save(current_user)
        return self.serialize_preferences(current_user)
