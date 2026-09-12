from __future__ import annotations

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.disposable_mailbox_manager.disposable_mailbox_manager import disposable_mailbox_manager
from orion.constants.constant import CONSTANTS
from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.shared_model.db_disposable_mailbox_model import db_disposable_mailbox_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_STATUS, PGP_KEY_TYPE, db_pgp_key_model
from orion.services.pgp_manager.pgp_manager import pgp_manager
from tests.model.fakes import RecordingEngine
from tests.scripts.disposable_mailbox_manager.helpers import USER, make_disposable, make_mailbox, make_manager, make_pgp_key


@pytest.mark.parametrize("value", ["", "   ", "x" * 5001])
def test_validate_identity_signature_rejects_invalid(value):
    with pytest.raises(HTTPException) as error:
        disposable_mailbox_manager.validate_identity_signature(value)
    assert error.value.status_code == 400


def test_validate_identity_signature_strips_valid_value():
    assert disposable_mailbox_manager.validate_identity_signature("  hello  ") == "hello"


@pytest.mark.anyio
async def test_get_owner_mailbox_raises_when_missing():
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.get_owner_mailbox(USER)
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_get_owner_mailbox_returns_active_mailbox():
    mailbox = make_mailbox()
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: mailbox}))
    assert await manager.get_owner_mailbox(USER) is mailbox


@pytest.mark.anyio
async def test_active_disposable_count_reads_collection():
    manager = make_manager(RecordingEngine(counts={db_disposable_mailbox_model: 4}))
    assert await manager.active_disposable_count(USER) == 4


@pytest.mark.anyio
async def test_saved_pgp_count_reads_collection():
    manager = make_manager(RecordingEngine(counts={db_pgp_key_model: 2}))
    assert await manager.saved_pgp_count(USER) == 2


@pytest.mark.anyio
async def test_generate_random_address_returns_unique_address():
    manager = make_manager(RecordingEngine(find_one={db_disposable_mailbox_model: None}))
    address = await manager.generate_random_address()
    local_part, _, domain = address.partition("@")
    assert domain == CONSTANTS.S_MAIL_DOMAIN.lower()
    assert len(local_part) == CONSTANTS.S_RANDOM_MAILBOX_LENGTH


@pytest.mark.anyio
async def test_generate_random_address_raises_when_exhausted():
    manager = make_manager(RecordingEngine(find_one={db_disposable_mailbox_model: object()}))
    with pytest.raises(HTTPException) as error:
        await manager.generate_random_address()
    assert error.value.status_code == 500


@pytest.mark.anyio
async def test_get_pgp_key_rejects_invalid_id():
    manager = make_manager(RecordingEngine())
    with pytest.raises(HTTPException) as error:
        await manager.get_pgp_key(USER, "not-an-object-id")
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_get_pgp_key_raises_when_not_found():
    manager = make_manager(RecordingEngine(find_one={db_pgp_key_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.get_pgp_key(USER, str(ObjectId()))
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_get_pgp_key_returns_owned_key():
    key = make_pgp_key()
    manager = make_manager(RecordingEngine(find_one={db_pgp_key_model: key}))
    assert await manager.get_pgp_key(USER, str(ObjectId())) is key


@pytest.mark.anyio
async def test_create_pgp_key_wraps_and_saves(monkeypatch):
    class FakePgp:
        @staticmethod
        async def generate_key_pair():
            return "PUB", "PRIV", "FINGER"

    class FakeKeyManager:
        @staticmethod
        def wrap(_value):
            return "WRAPPED"

    monkeypatch.setattr(pgp_manager, "get_instance", staticmethod(lambda: FakePgp()))
    monkeypatch.setattr(key_manager, "get_instance", staticmethod(lambda: FakeKeyManager()))
    engine = RecordingEngine()
    manager = make_manager(engine)
    mailbox = make_mailbox()

    record = await manager.create_pgp_key(USER, mailbox, PGP_KEY_TYPE.DISPOSABLE)

    assert record.fingerprint == "FINGER"
    assert record.public_key == "PUB"
    assert record.wrapped_private_key == "WRAPPED"
    assert record.key_type == PGP_KEY_TYPE.DISPOSABLE
    assert engine.saved == [record]


@pytest.mark.anyio
async def test_get_or_create_original_pgp_returns_existing():
    key = make_pgp_key(key_type=PGP_KEY_TYPE.ORIGINAL)
    engine = RecordingEngine(find_one={db_pgp_key_model: key})
    manager = make_manager(engine)
    assert await manager.get_or_create_original_pgp(USER, make_mailbox()) is key
    assert engine.saved == []


@pytest.mark.anyio
async def test_get_or_create_original_pgp_creates_when_missing():
    engine = RecordingEngine(find_one={db_pgp_key_model: None})
    manager = make_manager(engine)
    created = make_pgp_key(key_type=PGP_KEY_TYPE.ORIGINAL)

    async def fake_create(_user, _mailbox, _key_type):
        return created

    manager.create_pgp_key = fake_create
    assert await manager.get_or_create_original_pgp(USER, make_mailbox()) is created


@pytest.mark.anyio
async def test_generate_disposable_mailbox_rejects_when_limit_reached():
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})
    manager = make_manager(engine)

    async def fake_count(_user):
        return CONSTANTS.S_DISPOSABLE_MAILBOX_LIMIT

    manager.active_disposable_count = fake_count
    with pytest.raises(HTTPException) as error:
        await manager.generate_disposable_mailbox(USER, "signature")
    assert error.value.status_code == 409


@pytest.mark.anyio
async def test_generate_disposable_mailbox_rejects_unavailable_pgp_key():
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})
    manager = make_manager(engine)

    async def fake_count(_user):
        return 0

    async def fake_get_pgp(_user, _key_id):
        return make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, status=PGP_KEY_STATUS.ACTIVE)

    manager.active_disposable_count = fake_count
    manager.get_pgp_key = fake_get_pgp
    with pytest.raises(HTTPException) as error:
        await manager.generate_disposable_mailbox(USER, "signature", pgp_key_id=str(ObjectId()))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_generate_disposable_mailbox_creates_new_identity():
    mailbox = make_mailbox()
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox})
    manager = make_manager(engine)
    new_key = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, owner_mailbox_id=mailbox.id)

    async def fake_count(_user):
        return 0

    async def fake_create(_user, _mailbox, _key_type):
        return new_key

    async def fake_address():
        return "fresh@mail.orionintelligence.org"

    manager.active_disposable_count = fake_count
    manager.create_pgp_key = fake_create
    manager.generate_random_address = fake_address

    result = await manager.generate_disposable_mailbox(USER, "  my signature  ")

    assert result["type"] == "disposable"
    assert result["mailbox_address"] == "fresh@mail.orionintelligence.org"
    assert result["pgp_key_id"] == str(new_key.id)
    assert result["identity_signature"] == "my signature"


@pytest.mark.anyio
async def test_generate_disposable_mailbox_reactivates_available_saved_key():
    mailbox = make_mailbox()
    saved_key = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, status=PGP_KEY_STATUS.SAVED, owner_mailbox_id=mailbox.id)
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox})
    manager = make_manager(engine)

    async def fake_count(_user):
        return 0

    async def fake_get_pgp(_user, _key_id):
        return saved_key

    async def fake_address():
        return "reused@mail.orionintelligence.org"

    manager.active_disposable_count = fake_count
    manager.get_pgp_key = fake_get_pgp
    manager.generate_random_address = fake_address

    result = await manager.generate_disposable_mailbox(USER, "signature", pgp_key_id=str(saved_key.id))

    assert saved_key.status == PGP_KEY_STATUS.ACTIVE
    assert saved_key in engine.saved
    assert result["pgp_key_id"] == str(saved_key.id)


@pytest.mark.anyio
async def test_delete_disposable_mailbox_rejects_invalid_id():
    manager = make_manager(RecordingEngine())
    with pytest.raises(HTTPException) as error:
        await manager.delete_disposable_mailbox(USER, "bad-id", keep_pgp=False)
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_delete_disposable_mailbox_raises_when_not_found():
    manager = make_manager(RecordingEngine(find_one={db_disposable_mailbox_model: None}))
    with pytest.raises(HTTPException) as error:
        await manager.delete_disposable_mailbox(USER, str(ObjectId()), keep_pgp=False)
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_delete_disposable_mailbox_rejects_when_saved_limit_reached():
    mailbox = make_mailbox()
    pgp_key = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, owner_mailbox_id=mailbox.id)
    disposable = make_disposable(pgp_key.id, mailbox.id)
    engine = RecordingEngine(find_one={db_disposable_mailbox_model: disposable, db_pgp_key_model: pgp_key})
    manager = make_manager(engine)

    async def fake_saved_count(_user):
        return CONSTANTS.S_SAVED_DISPOSABLE_PGP_LIMIT

    manager.saved_pgp_count = fake_saved_count
    with pytest.raises(HTTPException) as error:
        await manager.delete_disposable_mailbox(USER, str(disposable.id), keep_pgp=True)
    assert error.value.status_code == 409


@pytest.mark.anyio
async def test_delete_disposable_mailbox_purges_matching_messages(monkeypatch):
    mailbox = make_mailbox()
    pgp_key = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, owner_mailbox_id=mailbox.id)
    disposable = make_disposable(pgp_key.id, mailbox.id)
    message = db_message_model(owner_mailbox_id=mailbox.id, sender_address="s@x.org", receiver_address=disposable.mailbox_address, subject="s", body="b", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX, raw_source_filename="raw.eml")
    engine = RecordingEngine(find_one={db_disposable_mailbox_model: disposable, db_pgp_key_model: pgp_key}, find={db_message_model: [message]})
    manager = make_manager(engine)

    purged = []

    class FakeAttachments:
        async def delete_message_attachments(self, message_id):
            purged.append(message_id)

        async def delete_raw_source(self, filename):
            purged.append(filename)

    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: FakeAttachments()))

    result = await manager.delete_disposable_mailbox(USER, str(disposable.id), keep_pgp=False)

    assert result == {"message": "Disposable email deleted"}
    assert message in engine.deleted
    assert disposable in engine.deleted
    assert pgp_key in engine.deleted
    assert message.id in purged


@pytest.mark.anyio
async def test_delete_disposable_mailbox_saves_pgp_when_kept(monkeypatch):
    mailbox = make_mailbox()
    pgp_key = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, owner_mailbox_id=mailbox.id)
    disposable = make_disposable(pgp_key.id, mailbox.id)
    engine = RecordingEngine(find_one={db_disposable_mailbox_model: disposable, db_pgp_key_model: pgp_key}, find={db_message_model: []})
    manager = make_manager(engine)

    async def fake_saved_count(_user):
        return 0

    manager.saved_pgp_count = fake_saved_count
    monkeypatch.setattr(attachment_manager, "get_instance", staticmethod(lambda: object()))

    await manager.delete_disposable_mailbox(USER, str(disposable.id), keep_pgp=True)

    assert pgp_key.status == PGP_KEY_STATUS.SAVED
    assert pgp_key in engine.saved
    assert pgp_key not in engine.deleted


@pytest.mark.anyio
async def test_delete_saved_pgp_key_rejects_non_saved_disposable():
    manager = make_manager(RecordingEngine())

    async def fake_get_pgp(_user, _key_id):
        return make_pgp_key(key_type=PGP_KEY_TYPE.ORIGINAL, status=PGP_KEY_STATUS.ACTIVE)

    manager.get_pgp_key = fake_get_pgp
    with pytest.raises(HTTPException) as error:
        await manager.delete_saved_pgp_key(USER, str(ObjectId()))
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_delete_saved_pgp_key_deletes_saved_key():
    key = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, status=PGP_KEY_STATUS.SAVED)
    engine = RecordingEngine()
    manager = make_manager(engine)

    async def fake_get_pgp(_user, _key_id):
        return key

    manager.get_pgp_key = fake_get_pgp
    result = await manager.delete_saved_pgp_key(USER, str(ObjectId()))
    assert result == {"message": "Saved PGP key deleted"}
    assert key in engine.deleted


@pytest.mark.anyio
async def test_list_saved_pgp_keys_maps_records():
    key = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, status=PGP_KEY_STATUS.SAVED)
    manager = make_manager(RecordingEngine(find={db_pgp_key_model: [key]}))
    result = await manager.list_saved_pgp_keys(USER)
    assert result == [{"id": str(key.id), "fingerprint": key.fingerprint, "created_at": key.created_at}]


@pytest.mark.anyio
async def test_list_sender_identities_combines_original_and_disposable():
    mailbox = make_mailbox()
    original_pgp = make_pgp_key(key_type=PGP_KEY_TYPE.ORIGINAL, owner_mailbox_id=mailbox.id)
    disposable_pgp = make_pgp_key(key_type=PGP_KEY_TYPE.DISPOSABLE, owner_mailbox_id=mailbox.id)
    disposable = make_disposable(disposable_pgp.id, mailbox.id)
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox}, find={db_disposable_mailbox_model: [disposable], db_pgp_key_model: [disposable_pgp]})
    manager = make_manager(engine)

    async def fake_original(_user, _mailbox):
        return original_pgp

    manager.get_or_create_original_pgp = fake_original
    result = await manager.list_sender_identities(USER)

    assert result["original"]["mailbox_address"] == mailbox.mailbox_address
    assert result["original"]["fingerprint"] == original_pgp.fingerprint
    assert len(result["disposable"]) == 1
    assert result["disposable"][0]["fingerprint"] == disposable_pgp.fingerprint
