from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.incoming_mail_manager.incoming_mail_manager import incoming_mail_manager
from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model


class FakeCollection:
    def __init__(self, stored_count):
        self.stored_count = stored_count
        self.queries = []

    async def count_documents(self, query):
        self.queries.append(query)
        return self.stored_count


class FakeCapEngine:
    def __init__(self, stored_count, evictable):
        self.collection = FakeCollection(stored_count)
        self.evictable = evictable
        self.deleted = []

    def get_collection(self, _model):
        return self.collection

    async def find(self, _model, _query, sort=None, limit=None):
        return self.evictable[:limit] if limit is not None else self.evictable

    async def delete(self, instance):
        self.deleted.append(instance)


class FakeAttachmentManager:
    def __init__(self):
        self.purged_messages = []
        self.purged_raw_sources = []

    async def delete_message_attachments(self, message_id):
        self.purged_messages.append(message_id)

    async def delete_raw_source(self, stored_filename):
        self.purged_raw_sources.append(stored_filename)


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


@pytest.mark.anyio
async def test_below_the_cap_accepts_without_deleting(monkeypatch):
    manager, mailbox, attachments = build_manager(MESSAGE_LIMITS.MAILBOX_MAX_MESSAGES - 1, [], monkeypatch)

    await manager.assert_mailbox_can_receive(mailbox)

    assert manager._engine.deleted == []
    assert attachments.purged_messages == []


@pytest.mark.anyio
async def test_drafts_are_excluded_from_the_counted_messages(monkeypatch):
    manager, mailbox, _attachments = build_manager(1, [], monkeypatch)

    await manager.stored_message_count(mailbox)

    assert manager._engine.collection.queries[-1]["folder"] == {"$ne": MESSAGE_FOLDER.DRAFTS.value}


@pytest.mark.anyio
async def test_at_cap_with_an_old_message_accepts_the_delivery(monkeypatch):
    mailbox_id = ObjectId()
    manager, mailbox, _attachments = build_manager(MESSAGE_LIMITS.MAILBOX_MAX_MESSAGES, [build_message(mailbox_id, age_days=30)], monkeypatch)

    await manager.assert_mailbox_can_receive(mailbox)

    assert manager._engine.deleted == []


@pytest.mark.anyio
async def test_at_cap_with_only_recent_mail_blocks_and_deletes_nothing(monkeypatch):
    manager, mailbox, attachments = build_manager(MESSAGE_LIMITS.MAILBOX_MAX_MESSAGES, [], monkeypatch)

    with pytest.raises(HTTPException) as error:
        await manager.assert_mailbox_can_receive(mailbox)

    assert error.value.status_code == 507
    assert "empty the trash" in error.value.detail
    assert manager._engine.deleted == []
    assert attachments.purged_messages == []


@pytest.mark.anyio
async def test_trim_removes_the_surplus_with_its_files(monkeypatch):
    mailbox_id = ObjectId()
    oldest = build_message(mailbox_id, age_days=30)
    manager, mailbox, attachments = build_manager(MESSAGE_LIMITS.MAILBOX_MAX_MESSAGES + 1, [oldest], monkeypatch)

    evicted = await manager.trim_mailbox_to_cap(mailbox)

    assert evicted == 1
    assert manager._engine.deleted == [oldest]
    assert attachments.purged_messages == [oldest.id]
    assert attachments.purged_raw_sources == ["old.eml"]


@pytest.mark.anyio
async def test_trim_is_a_no_op_at_or_below_the_cap(monkeypatch):
    manager, mailbox, attachments = build_manager(MESSAGE_LIMITS.MAILBOX_MAX_MESSAGES, [build_message(ObjectId(), age_days=30)], monkeypatch)

    assert await manager.trim_mailbox_to_cap(mailbox) == 0
    assert manager._engine.deleted == []
    assert attachments.purged_messages == []


@pytest.mark.anyio
async def test_trim_is_bounded_so_a_legacy_mailbox_drains_gradually(monkeypatch):
    mailbox_id = ObjectId()
    backlog = [build_message(mailbox_id, age_days=30 + index) for index in range(500)]
    manager, mailbox, _attachments = build_manager(5000, backlog, monkeypatch)

    evicted = await manager.trim_mailbox_to_cap(mailbox)

    assert evicted == MESSAGE_LIMITS.MAILBOX_EVICTION_BATCH
    assert len(manager._engine.deleted) == MESSAGE_LIMITS.MAILBOX_EVICTION_BATCH
