from __future__ import annotations


class FakeConfigController:
    async def get_config_int(self, _key):
        return 1


class FakeAntivirusManager:
    def __init__(self):
        self.scanned = []

    async def assert_clean(self, content, filename):
        self.scanned.append(filename)
