from __future__ import annotations

import pytest
from fastapi import HTTPException
from odmantic.exceptions import DuplicateKeyError

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.disposable_mailbox_manager.disposable_mailbox_manager import disposable_mailbox_manager
from orion.api.interactive.mailbox_manager.mailbox_manager import mailbox_manager
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from tests.model.fakes import FakeMailboxEngine, RecordingEngine
from tests.scripts.mailbox_manager.fakes import FakeDisposablePgp
from tests.scripts.mailbox_manager.helpers import USER, make_manager, make_mailbox


@pytest.mark.anyio
async def test_create_mailbox_uses_orion_account_username(monkeypatch):
    monkeypatch.setattr(CONSTANTS, "S_MAIL_DOMAIN", "mail.orionintelligence.org")
    monkeypatch.setattr(disposable_mailbox_manager, "get_instance", staticmethod(lambda: FakeDisposablePgp()))
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


@pytest.mark.anyio
async def test_create_mailbox_rejects_when_user_already_has_one():
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: make_mailbox()}))
    with pytest.raises(HTTPException) as error:
        await manager.create_mailbox(USER)
    assert error.value.status_code == 409


@pytest.mark.anyio
async def test_create_mailbox_maps_duplicate_key_error_to_conflict():
    engine = RecordingEngine(find_one={db_mailbox_model: None}, save_error=DuplicateKeyError.__new__(DuplicateKeyError))
    manager = make_manager(engine)
    with pytest.raises(HTTPException) as error:
        await manager.create_mailbox(USER)
    assert error.value.status_code == 409


@pytest.mark.anyio
async def test_get_user_mailbox_raises_when_missing():
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.get_user_mailbox(USER)
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_get_user_mailbox_returns_mailbox_details():
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: make_mailbox(signature="cheers")}))
    result = await manager.get_user_mailbox(USER)
    assert result == {"mailbox_address": "test1@mail.orionintelligence.org", "is_active": True, "signature": "cheers"}


@pytest.mark.anyio
async def test_update_mailbox_settings_raises_when_missing():
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.update_mailbox_settings(USER, "signature")
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_update_mailbox_settings_persists_stripped_signature():
    mailbox = make_mailbox()
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox})
    manager = make_manager(engine)
    result = await manager.update_mailbox_settings(USER, "  new signature  ")
    assert result["signature"] == "new signature"
    assert mailbox.signature == "new signature"
    assert mailbox in engine.saved


@pytest.mark.anyio
async def test_delete_mailbox_raises_when_missing():
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.delete_mailbox(USER)
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_delete_mailbox_purges_messages_and_related_records(monkeypatch):
    mailbox = make_mailbox()
    message = db_message_model(owner_mailbox_id=mailbox.id, sender_address="s@x.org", receiver_address=mailbox.mailbox_address, subject="s", body="b", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX, raw_source_filename="raw.eml")
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox}, find={db_message_model: [message]})
    manager = make_manager(engine)

    class FakeAttachments:
        async def delete_message_attachments(self, message_id):
            pass

        async def delete_raw_source(self, filename):
            pass

    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: FakeAttachments()))

    result = await manager.delete_mailbox(USER)

    assert result == {"message": "Mailbox and all stored mail deleted"}
    assert message in engine.deleted
    assert mailbox in engine.deleted
