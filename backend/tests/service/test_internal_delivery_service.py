from bson import ObjectId
from fastapi import HTTPException
import pytest

from orion.api.interactive.message_manager.message_manager import message_manager
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model


class FakeMailboxEngine:
    def __init__(self, addresses: list[str]):
        self.mailboxes = [db_mailbox_model(user_id=ObjectId(), mailbox_address=address) for address in addresses]

    async def find(self, *_args, **_kwargs):
        return self.mailboxes


def manager_with_mailboxes(addresses: list[str]) -> message_manager:
    manager = object.__new__(message_manager)
    manager._engine = FakeMailboxEngine(addresses)
    return manager


@pytest.mark.anyio
async def test_partition_recipient_addresses_routes_active_mailboxes_internally(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_MAIL_DOMAIN", "mail.orionintelligence.org")
    manager = manager_with_mailboxes(["test1@mail.orionintelligence.org", "test2@mail.orionintelligence.org"])

    internal, external = await manager.partition_recipient_addresses([
        "test1@mail.orionintelligence.org",
        "person@example.org",
        "test2@mail.orionintelligence.org",
    ])

    assert internal == ["test1@mail.orionintelligence.org", "test2@mail.orionintelligence.org"]
    assert external == ["person@example.org"]


@pytest.mark.anyio
async def test_partition_recipient_addresses_rejects_unknown_local_mailbox(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_MAIL_DOMAIN", "mail.orionintelligence.org")
    manager = manager_with_mailboxes([])

    with pytest.raises(HTTPException) as error:
        await manager.partition_recipient_addresses(["missing@mail.orionintelligence.org"])

    assert error.value.status_code == 404
    assert error.value.detail == "One or more local recipient mailboxes were not found"
