from __future__ import annotations

import pytest
from fastapi import HTTPException
from odmantic.exceptions import DuplicateKeyError

from orion.api.server.config_manager.config_enums import CONFIG_DEFAULTS, CONFIG_KEYS
from orion.services.mongo_manager.shared_model.db_system_config_model import db_system_config_model
from tests.scripts.config_controller.fakes import FakeConfigEngine
from tests.scripts.config_controller.helpers import build_controller, build_system_config_controller


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


@pytest.mark.anyio
async def test_get_settings_exposes_defaults_as_snake_case_fields():
    controller = build_system_config_controller()

    settings = await controller.get_settings()

    assert settings == {"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 5, "attachment_retention_hours": 48}


@pytest.mark.anyio
async def test_update_settings_persists_every_key():
    controller = build_system_config_controller()

    updated = await controller.update_settings({"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 4, "attachment_retention_hours": 24})

    assert updated == {"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 4, "attachment_retention_hours": 24}
    assert controller._engine.documents[CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS].value == 24
    assert len(controller._engine.saved) == 3


@pytest.mark.parametrize("key,value", [(CONFIG_KEYS.OUTGOING_ATTACHMENT_MAX_SIZE_MB, 0), (CONFIG_KEYS.OUTGOING_ATTACHMENT_MAX_SIZE_MB, 2), (CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB, 0), (CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB, 6), (CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS, 0), (CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS, 49)])
@pytest.mark.anyio
async def test_set_config_int_rejects_values_outside_the_allowed_range(key, value):
    controller = build_system_config_controller()

    with pytest.raises(HTTPException) as error:
        await controller.set_config_int(key, value)

    assert error.value.status_code == 400
    assert controller._engine.saved == []


@pytest.mark.anyio
async def test_set_config_int_rejects_unknown_key():
    controller = build_system_config_controller()

    with pytest.raises(HTTPException) as error:
        await controller.set_config_int("NOT_A_CONFIG_KEY", 5)

    assert error.value.status_code == 400
    assert controller._engine.saved == []


@pytest.mark.anyio
async def test_initialize_clamps_a_stored_value_above_the_current_maximum():
    controller = build_system_config_controller()
    controller._engine.documents[CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB].value = 25

    await controller.initialize()

    assert controller._engine.documents[CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB].value == 5
    assert await controller.get_settings() == {"outgoing_attachment_max_size_mb": 1, "incoming_attachment_max_size_mb": 5, "attachment_retention_hours": 48}


@pytest.mark.anyio
async def test_initialize_leaves_in_range_values_untouched():
    controller = build_system_config_controller()
    controller._engine.documents[CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS].value = 24

    await controller.initialize()

    assert controller._engine.documents[CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS].value == 24
    assert controller._engine.saved == []
