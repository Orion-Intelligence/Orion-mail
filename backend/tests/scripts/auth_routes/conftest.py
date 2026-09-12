from __future__ import annotations

import os

os.environ.setdefault("ORION_TESTING", "true")
os.environ.setdefault("MAIL_DOMAIN", "mail.orionintelligence.org")
os.environ.setdefault("SEED_LOCAL_TEST_MAILBOXES", "false")

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    return TestClient(main.app, base_url="http://localhost")


@pytest.fixture
def override():
    replaced: list = []

    def _override(dependency, replacement):
        main.app.dependency_overrides[dependency] = replacement
        replaced.append(dependency)

    yield _override
    for dependency in replaced:
        main.app.dependency_overrides.pop(dependency, None)
