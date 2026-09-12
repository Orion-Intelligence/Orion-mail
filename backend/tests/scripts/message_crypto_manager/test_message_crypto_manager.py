from __future__ import annotations

import pytest

from orion.services.encryption_manager.key_manager import key_manager
from tests.scripts.message_crypto_manager.helpers import PLAIN_BODY, PLAIN_HTML, PLAIN_SUBJECT, build_message, build_stack


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
