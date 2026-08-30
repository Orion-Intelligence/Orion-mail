import pytest
from bson import ObjectId

from orion.api.interactive.message_manager.message_manager import message_manager
from orion.services.encryption_manager.message_crypto_manager import message_crypto_manager
from orion.services.mongo_manager.shared_model.db_message_model import DELIVERY_STATUS, MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model


class FakeCryptoManager:
    def __init__(self):
        self.saved = []

    async def save_message(self, message):
        self.saved.append(message)
        return message


def build_sent_message():
    return db_message_model(owner_mailbox_id=ObjectId(), sender_address="me@mail.orionintelligence.org", receiver_address="them@example.com", subject="s", body="b", direction=MESSAGE_DIRECTION.OUTGOING, folder=MESSAGE_FOLDER.SENT, delivery_status=DELIVERY_STATUS.QUEUED)


@pytest.mark.anyio
async def test_a_failed_send_moves_into_the_inbox(monkeypatch):
    crypto = FakeCryptoManager()
    monkeypatch.setattr(message_crypto_manager, "get_instance", staticmethod(lambda: crypto))
    message = build_sent_message()

    await message_manager.mark_delivery_failed(message)

    assert message.folder == MESSAGE_FOLDER.INBOX
    assert message.delivery_status == DELIVERY_STATUS.FAILED
    assert crypto.saved == [message]


@pytest.mark.anyio
async def test_a_failed_send_remembers_it_belongs_in_sent(monkeypatch):
    crypto = FakeCryptoManager()
    monkeypatch.setattr(message_crypto_manager, "get_instance", staticmethod(lambda: crypto))
    message = build_sent_message()

    await message_manager.mark_delivery_failed(message)

    assert message.previous_folder == MESSAGE_FOLDER.SENT
    assert MESSAGE_FOLDER.SENT in message_manager.allowed_destinations(message)
