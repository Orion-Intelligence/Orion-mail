from __future__ import annotations

from orion.api.server.config_manager.config_controller import config_controller
from tests.scripts.config_controller.fakes import FakeSystemConfigEngine


def build_controller(engine):
    controller = object.__new__(config_controller)
    controller._engine = engine
    return controller


def build_system_config_controller():
    controller = object.__new__(config_controller)
    controller._engine = FakeSystemConfigEngine()
    return controller
