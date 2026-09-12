from __future__ import annotations

import asyncio

from orion.api.interactive.translation_manager import translation_manager as translation_module
from orion.api.interactive.translation_manager.translation_manager import translation_manager
from tests.scripts.translation_manager.fakes import FakeHttpxClient, FakeStreamResponse


def build_manager():
    manager = object.__new__(translation_manager)
    manager._request_semaphore = asyncio.Semaphore(4)
    return manager


def patch_httpx(monkeypatch, response: FakeStreamResponse):
    monkeypatch.setattr(translation_module.httpx, "Client", lambda *args, **kwargs: FakeHttpxClient(response))
