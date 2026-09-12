from __future__ import annotations


class FakeStreamResponse:
    def __init__(self, body: bytes = b"", raise_error: Exception | None = None):
        self._body = body
        self._raise_error = raise_error

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        if self._raise_error is not None:
            raise self._raise_error

    def iter_bytes(self):
        yield self._body


class FakeHttpxClient:
    def __init__(self, response: FakeStreamResponse):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stream(self, _method, _url, *, content, headers):
        return self._response
