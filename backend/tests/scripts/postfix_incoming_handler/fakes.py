from __future__ import annotations


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b"ok"):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body


class FakeConnection:
    def __init__(self, host, port, timeout=None, status: int = 200, body: bytes = b"ok", scheme: str = "http"):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.scheme = scheme
        self.status = status
        self.body = body
        self.requests: list[dict] = []
        self.closed = False

    def request(self, method, path, body=None, headers=None) -> None:
        self.requests.append({"method": method, "path": path, "body": body, "headers": headers})

    def getresponse(self) -> FakeResponse:
        return FakeResponse(self.status, self.body)

    def close(self) -> None:
        self.closed = True


class FailingResponseConnection(FakeConnection):
    def getresponse(self):
        raise OSError("connection reset")
