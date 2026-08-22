import pytest
from bson import ObjectId
from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from tests.fake_model.fakes import build_encryption_stack

RAW_EML = b"From: a@mail.orionintelligence.org\r\nSubject: Secret\r\n\r\nConfidential body\r\n"


def build_stack():
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="admin@mail.orionintelligence.org")
    message = db_message_model(owner_mailbox_id=mailbox.id, sender_address="a@x.org", receiver_address="b@x.org", subject="s", body="b", direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX)
    _crypto, engine = build_encryption_stack(mailbox=mailbox, message=message)

    manager = object.__new__(attachment_manager)
    manager._engine = engine
    return manager, engine, mailbox, message


@pytest.mark.anyio
async def test_owner_cipher_round_trips_file_bytes():
    manager, _engine, mailbox, _message = build_stack()

    cipher = await manager.owner_cipher(mailbox.id)
    assert cipher is not None
    sealed = cipher.encrypt_bytes(RAW_EML)

    assert RAW_EML not in sealed
    assert b"Confidential" not in sealed
    assert cipher.decrypt_bytes(sealed) == RAW_EML


@pytest.mark.anyio
async def test_message_cipher_matches_the_owning_mailbox_key():
    manager, _engine, mailbox, message = build_stack()

    by_message = await manager.message_cipher(message.id)
    by_mailbox = await manager.owner_cipher(mailbox.id)
    assert by_message is not None and by_mailbox is not None

    assert by_mailbox.decrypt_bytes(by_message.encrypt_bytes(RAW_EML)) == RAW_EML


@pytest.mark.anyio
async def test_read_raw_source_decrypts_only_when_flagged(tmp_path):
    manager, _engine, mailbox, message = build_stack()
    cipher = await manager.owner_cipher(mailbox.id)
    assert cipher is not None

    sealed_path = tmp_path / "sealed.eml"
    sealed_path.write_bytes(cipher.encrypt_bytes(RAW_EML))
    message.raw_source_encrypted = True
    assert await manager.read_raw_source(message, sealed_path) == RAW_EML

    legacy_path = tmp_path / "legacy.eml"
    legacy_path.write_bytes(RAW_EML)
    message.raw_source_encrypted = False
    assert await manager.read_raw_source(message, legacy_path) == RAW_EML


@pytest.mark.anyio
async def test_a_different_users_key_cannot_read_the_file():
    manager, engine, mailbox, _message = build_stack()
    owner_cipher = await manager.owner_cipher(mailbox.id)
    assert owner_cipher is not None
    sealed = owner_cipher.encrypt_bytes(RAW_EML)

    engine.mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="other@mail.orionintelligence.org")
    other_cipher = await manager.owner_cipher(engine.mailbox.id)
    assert other_cipher is not None

    with pytest.raises(Exception):
        other_cipher.decrypt_bytes(sealed)
