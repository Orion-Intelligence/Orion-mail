from __future__ import annotations

from typing import Any


class FakeRspamdClient:
    calls: list[dict[str, Any]] = []

    def __init__(self, status_code: int = 200, **_kwargs):
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, *, content, headers):
        FakeRspamdClient.calls.append({"url": url, "content": content, "headers": headers})
        return type("FakeRspamdResponse", (), {"status_code": self.status_code})()
