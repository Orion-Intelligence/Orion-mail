from __future__ import annotations

from typing import Any


class FakeMailTransport:
    def __init__(self, errors: dict[str, Any] | None = None):
        self.sent: list[dict[str, Any]] = []
        self.errors = errors or {}

    async def send(self, message, *, sender, recipients, hostname, port, username, password, start_tls, timeout):
        self.sent.append({"message": message, "sender": sender, "recipients": recipients, "hostname": hostname, "port": port, "username": username, "password": password, "start_tls": start_tls, "timeout": timeout})
        return self.errors, "250 Ok"
