from __future__ import annotations

from orion.services.encryption_manager.key_manager import key_manager
from tests.scripts.e2e_key_manager.helpers import VERIFIER, WRONG_VERIFIER


def test_secret_hash_is_salted_and_checkable():
    first, second = key_manager.hash_secret(VERIFIER), key_manager.hash_secret(VERIFIER)

    assert first != second and VERIFIER not in first
    assert key_manager.secret_matches(VERIFIER, first)
    assert not key_manager.secret_matches(WRONG_VERIFIER, first)
    assert not key_manager.secret_matches(VERIFIER, None)
    assert not key_manager.secret_matches(VERIFIER, "garbage")
