from __future__ import annotations

from typing import Any

from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


def build_user() -> db_user_model:
    return db_user_model(
        full_name="Abdul Mannan",
        email="abdul@orionintelligence.org",
        username="abdul",
        orion_user_id="orion-user-id",
        orion_tenant_id="orion-tenant-id",
        preferences={"theme": "light"},
    )


class FakeMailbox:
    def __init__(self, mailbox_address: str = "abdul@mail.orionintelligence.org"):
        self.mailbox_address = mailbox_address


class FakePreferenceInstance:
    def __init__(self, result: dict[str, Any]):
        self.result = result
        self.calls: list[dict] = []

    async def update_preferences(self, current_user, preferences):
        self.calls.append(preferences)
        return self.result


class FakeIdentityClient:
    def __init__(self, exchange_result: dict[str, Any] | None = None):
        self.exchange_result = exchange_result or {}
        self.revoked: list[str] = []

    async def exchange(self, code, redirect_uri):
        return self.exchange_result

    async def revoke(self, token):
        self.revoked.append(token)


class FakeIdentityManager:
    def __init__(self, user):
        self.user = user
        self.linked: list[dict] = []

    async def link_identity(self, identity):
        self.linked.append(identity)
        return self.user
