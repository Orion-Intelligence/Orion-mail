import pytest
from fastapi import HTTPException

from orion.api.server.config_manager.config_controller import config_controller
from orion.api.server.config_manager.config_enums import CONFIG_DEFAULTS, CONFIG_KEYS
from orion.services.mongo_manager.shared_model.db_system_config_model import db_system_config_model


class FakeConfigEngine:
    def __init__(self):
        self.documents = {config["key"]: db_system_config_model(**config) for config in CONFIG_DEFAULTS.VALUES}
        self.saved = []

    async def find_one(self, _model, query):
        return self.documents.get(dict(query)["key"]["$eq"])

    async def save(self, config):
        self.documents[config.key] = config
        self.saved.append(config)
        return config


def build_controller():
    controller = object.__new__(config_controller)
    controller._engine = FakeConfigEngine()
    return controller


@pytest.mark.anyio
async def test_get_settings_exposes_defaults_as_snake_case_fields():
    controller = build_controller()

    settings = await controller.get_settings()

    assert settings == {"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 5, "attachment_retention_hours": 48}


@pytest.mark.anyio
async def test_update_settings_persists_every_key():
    controller = build_controller()

    updated = await controller.update_settings({"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 4, "attachment_retention_hours": 24})

    assert updated == {"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 4, "attachment_retention_hours": 24}
    assert controller._engine.documents[CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS].value == 24
    assert len(controller._engine.saved) == 3


@pytest.mark.parametrize("key,value", [(CONFIG_KEYS.OUTGOING_ATTACHMENT_MAX_SIZE_MB, 0), (CONFIG_KEYS.OUTGOING_ATTACHMENT_MAX_SIZE_MB, 2), (CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB, 0), (CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB, 6), (CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS, 0), (CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS, 49)])
@pytest.mark.anyio
async def test_set_config_int_rejects_values_outside_the_allowed_range(key, value):
    controller = build_controller()

    with pytest.raises(HTTPException) as error:
        await controller.set_config_int(key, value)

    assert error.value.status_code == 400
    assert controller._engine.saved == []


@pytest.mark.anyio
async def test_set_config_int_rejects_unknown_key():
    controller = build_controller()

    with pytest.raises(HTTPException) as error:
        await controller.set_config_int("NOT_A_CONFIG_KEY", 5)

    assert error.value.status_code == 400
    assert controller._engine.saved == []


@pytest.mark.anyio
async def test_initialize_clamps_a_stored_value_above_the_current_maximum():
    controller = build_controller()
    controller._engine.documents[CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB].value = 25

    await controller.initialize()

    assert controller._engine.documents[CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB].value == 5
    assert await controller.get_settings() == {"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 5, "attachment_retention_hours": 48}


@pytest.mark.anyio
async def test_initialize_leaves_in_range_values_untouched():
    controller = build_controller()
    controller._engine.documents[CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS].value = 24

    await controller.initialize()

    assert controller._engine.documents[CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS].value == 24
    assert controller._engine.saved == []
