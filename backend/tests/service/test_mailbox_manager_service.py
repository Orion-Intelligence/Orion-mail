import pytest
from fastapi import HTTPException

from orion.api.interactive.mailbox_manager.mailbox_manager import mailbox_manager
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class FakeMailboxEngine:
    def __init__(self):
        self.saved_mailbox = None

    @staticmethod
    async def find_one(*_args, **_kwargs):
        return None

    async def save(self, mailbox):
        self.saved_mailbox = mailbox
        return mailbox


@pytest.mark.anyio
async def test_create_mailbox_uses_orion_account_username(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_MAIL_DOMAIN", "mail.orionintelligence.org")
    engine = FakeMailboxEngine()
    manager = object.__new__(mailbox_manager)
    manager._engine = engine
    user = db_user_model(full_name="Administrator", email="admin@orionintelligence.org", username="Admin")

    result = await manager.create_mailbox(current_user=user)

    assert isinstance(engine.saved_mailbox, db_mailbox_model)
    assert engine.saved_mailbox.user_id == user.id
    assert result["mailbox_address"] == "admin@mail.orionintelligence.org"


@pytest.mark.anyio
async def test_create_mailbox_rejects_invalid_orion_username():
    manager = object.__new__(mailbox_manager)
    manager._engine = FakeMailboxEngine()
    user = db_user_model(full_name="Administrator", email="admin@orionintelligence.org", username="invalid username")

    with pytest.raises(HTTPException) as error:
        await manager.create_mailbox(current_user=user)

    assert error.value.status_code == 422
