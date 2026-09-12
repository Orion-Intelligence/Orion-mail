from __future__ import annotations

from tests.model.fakes import FakePgpKey


class FakeDisposablePgp:
    @staticmethod
    async def get_or_create_original_pgp(_current_user, _mailbox):
        return FakePgpKey()
