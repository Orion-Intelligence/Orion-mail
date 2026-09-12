from __future__ import annotations

from orion.api.interactive.mailbox_manager.mailbox_manager import mailbox_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")


def make_manager(engine):
    manager = object.__new__(mailbox_manager)
    manager._engine = engine
    return manager


def make_mailbox(signature=""):
    mailbox = db_mailbox_model(user_id=USER.id, mailbox_address="test1@mail.orionintelligence.org")
    mailbox.signature = signature
    return mailbox
