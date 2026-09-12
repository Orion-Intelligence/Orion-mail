from __future__ import annotations

import pytest

from orion.services.antivirus_manager.antivirus_manager import antivirus_manager


@pytest.fixture
def manager():
    return antivirus_manager.get_instance()
