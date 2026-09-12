from __future__ import annotations

from orion.services.pgp_manager import pgp_manager as pgp_module
from tests.scripts.pgp_manager.fakes import FakeProcess


def patch_subprocess(monkeypatch, process: FakeProcess):
    async def fake_exec(_program, *_args, **_kwargs):
        return process

    monkeypatch.setattr(pgp_module.asyncio, "create_subprocess_exec", fake_exec)
