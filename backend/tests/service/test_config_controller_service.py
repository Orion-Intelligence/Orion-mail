import pytest
from fastapi import HTTPException
from odmantic.exceptions import DuplicateKeyError

from orion.api.server.config_manager.config_controller import config_controller
from orion.api.server.config_manager.config_enums import CONFIG_DEFAULTS, CONFIG_KEYS
from orion.services.mongo_manager.shared_model.db_system_config_model import db_system_config_model


class FakeConfigEngine:
    def __init__(self, documents=None, save_error=None):
        self.documents = documents or {}
        self.save_error = save_error
        self.saved = []

    async def find_one(self, _model, query):
        return self.documents.get(dict(query)["key"]["$eq"])

    async def save(self, config):
        if self.save_error is not None:
            raise self.save_error
        self.documents[config.key] = config
        self.saved.append(config)
        return config


def build_controller(engine):
    controller = object.__new__(config_controller)
    controller._engine = engine
    return controller


@pytest.mark.anyio
async def test_initialize_saves_every_missing_default():
    engine = FakeConfigEngine()
    controller = build_controller(engine)

    await controller.initialize()

    assert len(engine.saved) == len(CONFIG_DEFAULTS.VALUES)


@pytest.mark.anyio
async def test_initialize_ignores_duplicate_key_error():
    engine = FakeConfigEngine(save_error=DuplicateKeyError.__new__(DuplicateKeyError))
    controller = build_controller(engine)

    await controller.initialize()

    assert engine.saved == []


@pytest.mark.anyio
async def test_clamp_stored_config_ignores_keys_without_limits():
    engine = FakeConfigEngine()
    controller = build_controller(engine)
    stored = db_system_config_model(key="UNMANAGED_KEY", value=999, value_type="integer")

    await controller.clamp_stored_config(stored)

    assert engine.saved == []


@pytest.mark.anyio
async def test_clamp_stored_config_falls_back_to_minimum_for_non_numeric_value():
    engine = FakeConfigEngine()
    controller = build_controller(engine)
    stored = db_system_config_model(key=CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS, value="not-a-number", value_type="integer")

    await controller.clamp_stored_config(stored)

    assert stored.value == 1
    assert stored in engine.saved


@pytest.mark.anyio
async def test_get_config_value_raises_when_config_missing():
    controller = build_controller(FakeConfigEngine())
    with pytest.raises(HTTPException) as error:
        await controller.get_config_value(CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS)
    assert error.value.status_code == 500


@pytest.mark.anyio
async def test_get_config_int_raises_on_non_integer_value():
    engine = FakeConfigEngine(documents={CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS: db_system_config_model(key=CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS, value="abc", value_type="integer")})
    controller = build_controller(engine)
    with pytest.raises(HTTPException) as error:
        await controller.get_config_int(CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS)
    assert error.value.status_code == 500


@pytest.mark.anyio
async def test_set_config_int_raises_when_config_missing():
    controller = build_controller(FakeConfigEngine())
    with pytest.raises(HTTPException) as error:
        await controller.set_config_int(CONFIG_KEYS.OUTGOING_ATTACHMENT_MAX_SIZE_MB, 1)
    assert error.value.status_code == 500
