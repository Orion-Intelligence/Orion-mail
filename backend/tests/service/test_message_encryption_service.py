import pytest
from bson import ObjectId
from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from tests.fake_model.fakes import build_encryption_stack

PLAIN_SUBJECT = "Quarterly report"
PLAIN_BODY = "The figures are attached. Treat as confidential."
PLAIN_HTML = "<p>The figures are attached.</p>"


def build_stack():
    mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="admin@mail.orionintelligence.org")
    crypto, engine = build_encryption_stack(mailbox=mailbox)
    return crypto, engine, mailbox


def build_message(mailbox):
    return db_message_model(owner_mailbox_id=mailbox.id, sender_address="a@mail.orionintelligence.org", receiver_address="b@mail.orionintelligence.org", subject=PLAIN_SUBJECT, body=PLAIN_BODY, body_html=PLAIN_HTML, direction=MESSAGE_DIRECTION.INCOMING, folder=MESSAGE_FOLDER.INBOX)


@pytest.mark.anyio
async def test_encrypt_replaces_content_and_decrypt_restores_it():
    crypto, _engine, mailbox = build_stack()
    message = build_message(mailbox)

    await crypto.encrypt_message(message)

    assert message.is_encrypted is True
    assert message.sealed_key
    assert message.subject != PLAIN_SUBJECT
    assert PLAIN_BODY not in message.body
    assert PLAIN_HTML not in (message.body_html or "")
    assert message.sender_address == "a@mail.orionintelligence.org"

    await crypto.decrypt_message(message)

    assert (message.subject, message.body, message.body_html) == (PLAIN_SUBJECT, PLAIN_BODY, PLAIN_HTML)


@pytest.mark.anyio
async def test_save_message_persists_ciphertext_and_leaves_plaintext_in_memory():
    crypto, engine, mailbox = build_stack()
    message = build_message(mailbox)

    await crypto.save_message(message)

    assert engine.saved_messages == [message]
    assert message.subject == PLAIN_SUBJECT
    assert message.is_encrypted is False


@pytest.mark.anyio
async def test_encrypt_is_idempotent_and_never_double_wraps():
    crypto, _engine, mailbox = build_stack()
    message = build_message(mailbox)

    await crypto.encrypt_message(message)
    first_cipher, first_seal = message.body, message.sealed_key
    await crypto.encrypt_message(message)

    assert (message.body, message.sealed_key) == (first_cipher, first_seal)

    await crypto.decrypt_message(message)
    assert message.body == PLAIN_BODY


@pytest.mark.anyio
async def test_decrypt_is_a_noop_for_legacy_plaintext_rows():
    crypto, _engine, mailbox = build_stack()
    message = build_message(mailbox)

    await crypto.decrypt_message(message)

    assert (message.subject, message.body) == (PLAIN_SUBJECT, PLAIN_BODY)


@pytest.mark.anyio
async def test_each_message_gets_a_distinct_sealed_content_key():
    crypto, _engine, mailbox = build_stack()
    first, second = build_message(mailbox), build_message(mailbox)

    await crypto.encrypt_message(first)
    await crypto.encrypt_message(second)

    assert first.sealed_key != second.sealed_key
    assert first.body != second.body


@pytest.mark.anyio
async def test_content_is_unreadable_without_the_matching_private_key():
    crypto, engine, mailbox = build_stack()
    message = build_message(mailbox)
    await crypto.encrypt_message(message)

    engine.keys.clear()
    key_manager.get_instance()._private_key_cache.clear()

    await crypto.decrypt_message(message)

    assert message.body != PLAIN_BODY
    assert message.is_encrypted is True
