from __future__ import annotations

import pytest
from fastapi import HTTPException

from orion.api.interactive.messenger_manager.messenger_enums import MESSENGER_LIMITS, MESSENGER_TEXT
from orion.api.interactive.messenger_manager.messenger_manager import messenger_manager
from orion.api.interactive.messenger_manager.models.messenger_param_model import MessengerSendRequest
from tests.scripts.messenger_manager.helpers import E2E_BODY, LEGACY_BODY, OUTSIDER, RECEIVER, SENDER, make_message


def test_end_to_end_chat_is_returned_as_ciphertext_to_both_parties():
    message = make_message(E2E_BODY)

    assert messenger_manager.stored_body_for_user(message, SENDER) == E2E_BODY
    assert messenger_manager.stored_body_for_user(message, RECEIVER) == E2E_BODY


def test_chat_from_before_end_to_end_is_never_decrypted_by_the_server():
    assert messenger_manager.stored_body_for_user(make_message(LEGACY_BODY), RECEIVER) == MESSENGER_TEXT.LEGACY_CHAT


def test_outsider_cannot_read_a_chat():
    with pytest.raises(HTTPException) as error:
        messenger_manager.stored_body_for_user(make_message(E2E_BODY), OUTSIDER)

    assert error.value.status_code == 403


def test_chat_request_allows_ciphertext_up_to_the_limit_only():
    ciphertext = E2E_BODY.replace("wcBMA", "A" * 9000)

    assert MessengerSendRequest(receiver_user_id="1", body=ciphertext).body == ciphertext
    with pytest.raises(ValueError):
        MessengerSendRequest(receiver_user_id="1", body="a" * (MESSENGER_LIMITS.BODY_MAX_LENGTH + 1))
