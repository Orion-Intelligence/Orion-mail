from __future__ import annotations

from orion.api.interactive.preference_manager.preference_manager import preference_manager
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from tests.scripts.preference_manager.fakes import FakeUserEngine


def build_manager():
    manager = object.__new__(preference_manager)
    manager._engine = FakeUserEngine()
    return manager


def build_user():
    return db_user_model(full_name="Administrator", email="admin@orionintelligence.org", username="Admin")
