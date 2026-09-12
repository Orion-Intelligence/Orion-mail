from __future__ import annotations

from bson import ObjectId

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.message_manager.message_manager import message_manager
from orion.api.interactive.sender_safety_manager.sender_safety_manager import sender_safety_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import DELIVERY_STATUS, MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_STATUS, PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.services.spam_manager.spam_manager import spam_manager
from tests.model.fakes import RecordingEngine
from tests.scripts.message_manager.fakes import FakeMailboxEngine

USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")


def default_mailbox(signature=""):
    return db_mailbox_model(user_id=ObjectId(), mailbox_address="test1@mail.orionintelligence.org", signature=signature)


def make_message(**overrides):
    defaults = dict(
        owner_mailbox_id=ObjectId(),
        sender_address="sender@example.org",
        receiver_address="test1@mail.orionintelligence.org",
        subject="Subject",
        body="Body",
        direction=MESSAGE_DIRECTION.INCOMING,
        folder=MESSAGE_FOLDER.INBOX,
    )
    defaults.update(overrides)
    return db_message_model(**defaults)


def make_pgp_key(owner_mailbox_id=None):
    return db_pgp_key_model(user_id=USER.id, owner_mailbox_id=owner_mailbox_id or ObjectId(), key_type=PGP_KEY_TYPE.ORIGINAL, status=PGP_KEY_STATUS.ACTIVE, fingerprint=ObjectId().binary.hex(), public_key="PUB", wrapped_private_key="WRAP")


def make_manager(message=None, mailbox=None, engine=None):
    manager = object.__new__(message_manager)
    box = mailbox if mailbox is not None else default_mailbox()

    async def fake_mailbox(_user):
        return box

    async def fake_owned(_mailbox, _message_id):
        return message

    manager.get_active_user_mailbox = fake_mailbox
    manager.get_owned_message = fake_owned
    manager._engine = engine if engine is not None else RecordingEngine()
    return manager


def patch_safety(monkeypatch, safety):
    monkeypatch.setattr(sender_safety_manager, "get_instance", staticmethod(lambda: safety))


def patch_attachments(monkeypatch, attachments):
    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: attachments))


def patch_spam(monkeypatch, spam):
    monkeypatch.setattr(spam_manager, "get_instance", staticmethod(lambda: spam))


def prepare_deep_send_manager(key, owned_message):
    manager = make_manager(engine=RecordingEngine(find_one={db_pgp_key_model: key}))

    async def no_op_quota(_mailbox):
        return None

    async def fake_partition(addresses):
        return ([], list(addresses))

    async def fake_owned(_mailbox, _message_id):
        return owned_message

    manager.enforce_send_quota = no_op_quota
    manager.enforce_storage_quota = no_op_quota
    manager.partition_recipient_addresses = fake_partition
    manager.get_owned_message = fake_owned
    return manager


def make_scheduling_manager(message):
    manager = object.__new__(message_manager)
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="test1@mail.orionintelligence.org")

    async def fake_mailbox(_user):
        return mailbox

    async def fake_owned(_mailbox, _message_id):
        return message

    manager.get_active_user_mailbox = fake_mailbox
    manager.get_owned_message = fake_owned
    return manager


def search_manager(engine):
    manager = object.__new__(message_manager)
    manager._engine = engine
    return manager


def manager_with_mailboxes(addresses: list[str]) -> message_manager:
    manager = object.__new__(message_manager)
    manager._engine = FakeMailboxEngine(addresses)
    return manager


def build_sent_message():
    return db_message_model(owner_mailbox_id=ObjectId(), sender_address="me@mail.orionintelligence.org", receiver_address="them@example.com", subject="s", body="b", direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT, delivery_status=DELIVERY_STATUS.QUEUED)
