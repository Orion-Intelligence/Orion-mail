from __future__ import annotations

import pytest
from fastapi import HTTPException

from orion.api.interactive.e2e_key_manager.e2e_key_manager import e2e_key_manager
from orion.api.interactive.message_manager.message_manager import message_manager
from tests.scripts.message_manager.helpers import ALICE, BOB, E2E_BODY, FOREIGN_PGP_BODY, patch_e2e_keys


def test_body_detector_needs_the_orion_marker():
    assert e2e_key_manager.is_e2e_body(E2E_BODY)
    assert not e2e_key_manager.is_e2e_body(FOREIGN_PGP_BODY)
    assert not e2e_key_manager.is_e2e_body("hello " + E2E_BODY)
    assert not e2e_key_manager.is_e2e_body("hello")


@pytest.mark.anyio
async def test_plain_mail_between_keyed_users_is_refused(monkeypatch):
    patch_e2e_keys(monkeypatch)

    with pytest.raises(HTTPException) as error:
        await message_manager.assert_end_to_end_when_possible(object(), "original", [ALICE, BOB], [], "hello")

    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_encrypted_mail_between_keyed_users_is_allowed(monkeypatch):
    patch_e2e_keys(monkeypatch)

    await message_manager.assert_end_to_end_when_possible(object(), "original", [ALICE, BOB], [], E2E_BODY)


@pytest.mark.anyio
@pytest.mark.parametrize("sender_has_key, keyed, identity, external", [
    (False, (ALICE, BOB), "original", []),
    (True, (ALICE,), "original", []),
    (True, (ALICE, BOB), "disposable", []),
    (True, (ALICE, BOB), "original", ["someone@gmail.com"]),
])
async def test_plain_mail_is_allowed_when_end_to_end_is_impossible(monkeypatch, sender_has_key, keyed, identity, external):
    patch_e2e_keys(monkeypatch, sender_has_key, keyed)

    await message_manager.assert_end_to_end_when_possible(object(), identity, [ALICE, BOB], external, "hello")
