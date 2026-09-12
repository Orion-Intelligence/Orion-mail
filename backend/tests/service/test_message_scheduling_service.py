from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.message_manager.message_manager import message_manager
from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.services.encryption_manager import message_crypto_manager as crypto_module
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import (
    MESSAGE_DIRECTION,
    MESSAGE_FOLDER,
    db_message_model,
)
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model

USER = db_user_model(full_name="Test One", email="test1@orionintelligence.org", username="test1")


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


def make_manager(message):
    manager = object.__new__(message_manager)
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="test1@mail.orionintelligence.org")

    async def fake_mailbox(_user):
        return mailbox

    async def fake_owned(_mailbox, _message_id):
        return message

    manager.get_active_user_mailbox = fake_mailbox
    manager.get_owned_message = fake_owned
    return manager


@pytest.fixture(autouse=True)
def fake_save_message(monkeypatch):
    class FakeCrypto:
        async def save_message(self, message):
            return message

    monkeypatch.setattr(crypto_module.message_crypto_manager, "get_instance", staticmethod(lambda: FakeCrypto()))


@pytest.mark.anyio
async def test_snooze_rejects_outgoing_message():
    manager = make_manager(make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT))
    with pytest.raises(HTTPException) as error:
        await manager.snooze_message(USER, "id", datetime.now(UTC) + timedelta(hours=1))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_snooze_rejects_past_time():
    manager = make_manager(make_message())
    with pytest.raises(HTTPException) as error:
        await manager.snooze_message(USER, "id", datetime.now(UTC) - timedelta(hours=1))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_snooze_sets_wake_time_and_moves_to_inbox():
    manager = make_manager(make_message(folder=MESSAGE_FOLDER.ARCHIVE))
    result = await manager.snooze_message(USER, "id", datetime.now(UTC) + timedelta(hours=2))
    assert result["snoozed_until"] is not None
    assert result["folder"] == MESSAGE_FOLDER.INBOX


@pytest.mark.anyio
async def test_schedule_rejects_non_draft():
    manager = make_manager(make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT))
    with pytest.raises(HTTPException) as error:
        await manager.schedule_message(USER, "id", datetime.now(UTC) + timedelta(hours=1))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_schedule_rejects_past_time():
    manager = make_manager(make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS))
    with pytest.raises(HTTPException) as error:
        await manager.schedule_message(USER, "id", datetime.now(UTC) - timedelta(hours=1))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_schedule_rejects_too_far_ahead():
    manager = make_manager(make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS))
    with pytest.raises(HTTPException) as error:
        await manager.schedule_message(USER, "id", datetime.now(UTC) + timedelta(days=MESSAGE_LIMITS.MAX_SCHEDULE_DAYS + 5))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_schedule_rejects_missing_receiver():
    manager = make_manager(make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS, receiver_address=""))
    with pytest.raises(HTTPException) as error:
        await manager.schedule_message(USER, "id", datetime.now(UTC) + timedelta(hours=2))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_schedule_sets_send_time_on_valid_draft():
    manager = make_manager(make_message(direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.DRAFTS))
    result = await manager.schedule_message(USER, "id", datetime.now(UTC) + timedelta(days=1))
    assert result["scheduled_at"] is not None
