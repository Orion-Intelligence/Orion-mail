from __future__ import annotations

import pytest

from orion.services.encryption_manager import message_crypto_manager as crypto_module
from tests.scripts.message_manager.fakes import FakeCrypto


@pytest.fixture(autouse=True)
def fake_crypto(monkeypatch):
    monkeypatch.setattr(crypto_module.message_crypto_manager, "get_instance", staticmethod(lambda: FakeCrypto()))
