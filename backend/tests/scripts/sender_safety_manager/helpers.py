from __future__ import annotations

from bson import ObjectId

from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from tests.scripts.sender_safety_manager.fakes import FakeEngine

USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")


def make_manager(by_model):
    manager = object.__new__(sender_safety_manager)
    manager._engine = FakeEngine(by_model)
    return manager


def message_from(sender: str):
    return db_message_model(
        owner_mailbox_id=ObjectId(),
        sender_address=sender,
        receiver_address="test1@mail.orionintelligence.org",
        subject="s",
        body="b",
        direction=MESSAGE_DIRECTION.INCOMING,
        folder=MESSAGE_FOLDER.INBOX,
    )
