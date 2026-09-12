from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bson import ObjectId

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.incoming_mail_manager.incoming_mail_manager import incoming_mail_manager
from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.services.encryption_manager.message_crypto_manager import message_crypto_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from tests.scripts.incoming_mail_manager.fakes import FakeAttachmentManager, FakeCapEngine, FakeCrypto


def make_manager(engine):
    manager = object.__new__(incoming_mail_manager)
    manager._engine = engine
    return manager


def make_mailbox():
    return db_mailbox_model(user_id=ObjectId(), mailbox_address="test1@mail.orionintelligence.org")


def patch_crypto(monkeypatch):
    crypto = FakeCrypto()
    monkeypatch.setattr(message_crypto_manager, "get_instance", staticmethod(lambda: crypto))
    return crypto


def patch_sender_safety(monkeypatch, blocked: bool):
    class FakeSenderSafety:
        async def is_domain_blocked_for_user(self, _user_id, _sender):
            return blocked

    monkeypatch.setattr(sender_safety_manager, "get_instance", staticmethod(lambda: FakeSenderSafety()))


def build_message(mailbox_id, age_days, raw_source_filename="old.eml"):
    message = db_message_model(owner_mailbox_id=mailbox_id, sender_address="a@x.org", receiver_address="b@x.org", subject="s", body="b", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX, raw_source_filename=raw_source_filename)
    message.created_at = datetime.now(UTC) - timedelta(days=age_days)
    return message


def build_manager(stored_count, evictable, monkeypatch):
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="admin@mail.orionintelligence.org")
    manager = object.__new__(incoming_mail_manager)
    manager._engine = FakeCapEngine(stored_count, evictable)
    attachments = FakeAttachmentManager()
    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: attachments))
    return manager, mailbox, attachments
