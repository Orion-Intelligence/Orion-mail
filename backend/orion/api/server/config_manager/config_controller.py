from datetime import UTC, datetime

from fastapi import HTTPException, status
from odmantic.exceptions import DuplicateKeyError

from orion.api.server.config_manager.config_enums import CONFIG_DEFAULTS, CONFIG_FIELDS, CONFIG_LIMITS
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_system_config_model import db_system_config_model


class config_controller:
    __instance = None

    @staticmethod
    def get_instance():
        if config_controller.__instance is None:
            config_controller()
        return config_controller.__instance

    def __init__(self):
        if config_controller.__instance is not None:
            raise Exception("This class is a singleton!")
        config_controller.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    async def initialize(self) -> None:
        for config in CONFIG_DEFAULTS.VALUES:
            stored = await self._engine.find_one(db_system_config_model, db_system_config_model.key == config["key"])
            if stored is not None:
                await self.clamp_stored_config(stored)
                continue
            try:
                await self._engine.save(db_system_config_model(**config))
            except DuplicateKeyError:
                continue

    async def clamp_stored_config(self, stored: db_system_config_model) -> None:
        limits = CONFIG_LIMITS.RANGES.get(stored.key)
        if limits is None:
            return

        minimum, maximum = limits
        try:
            value = int(stored.value)
        except (TypeError, ValueError):
            value = minimum

        clamped = min(max(value, minimum), maximum)
        if clamped == stored.value:
            return

        stored.value = clamped
        stored.updated_at = datetime.now(UTC)
        await self._engine.save(stored)

    async def get_config_value(self, key: str):
        config = await self._engine.find_one(db_system_config_model, db_system_config_model.key == key)
        if config is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"System configuration missing: {key}")
        return config.value

    async def get_config_int(self, key: str) -> int:
        value = await self.get_config_value(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Invalid integer configuration: {key}")

    async def set_config_int(self, key: str, value: int) -> int:
        if key not in CONFIG_LIMITS.RANGES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown configuration key: {key}")

        minimum, maximum = CONFIG_LIMITS.RANGES[key]
        if value < minimum or value > maximum:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{key} must be between {minimum} and {maximum}")

        config = await self._engine.find_one(db_system_config_model, db_system_config_model.key == key)
        if config is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"System configuration missing: {key}")

        config.value = value
        config.updated_at = datetime.now(UTC)
        await self._engine.save(config)
        return value

    async def get_settings(self) -> dict:
        return {field_name: await self.get_config_int(key) for field_name, key in CONFIG_FIELDS.NAMES.items()}

    async def update_settings(self, settings: dict) -> dict:
        for field_name, key in CONFIG_FIELDS.NAMES.items():
            await self.set_config_int(key, settings[field_name])
        return await self.get_settings()
