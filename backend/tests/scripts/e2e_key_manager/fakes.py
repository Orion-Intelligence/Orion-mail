from __future__ import annotations


class FakePgpInspector:
    def __init__(self, fingerprint: str, locked: bool = True):
        self.fingerprint = fingerprint
        self.locked = locked
        self.inspected: list[str] = []

    async def key_fingerprint(self, armored_key: str) -> str | None:
        self.inspected.append(armored_key)
        return self.fingerprint

    async def private_key_is_locked(self, _armored_key: str) -> bool:
        return self.locked


class FakeIdentityClient:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[str, str | None]] = []

    async def set_mail_passphrase(self, session_token: str, verifier: str | None) -> None:
        self.calls.append((session_token, verifier))
        if self.error is not None:
            raise self.error


class FakeKeyWrapper:
    @staticmethod
    def wrap(value: str) -> str:
        return f"wrapped:{value}"

    @staticmethod
    def unwrap(wrapped: str) -> str:
        return wrapped.removeprefix("wrapped:")
