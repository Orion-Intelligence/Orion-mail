from __future__ import annotations

from typing import Any


class FakeMailTransport:
    def __init__(self, errors: dict[str, Any] | None = None):
        self.sent: list[dict[str, Any]] = []
        self.errors = errors or {}

    async def send(self, message, *, sender, recipients, hostname, port, username, password, start_tls, timeout):
        self.sent.append({"message": message, "sender": sender, "recipients": recipients, "hostname": hostname, "port": port, "username": username, "password": password, "start_tls": start_tls, "timeout": timeout})
        return self.errors, "250 Ok"


class FakeKeyEngine:
    def __init__(self, mailbox=None, message=None):
        self.mailbox = mailbox
        self.message = message
        self.keys: dict[str, Any] = {}
        self.saved_messages: list[Any] = []

    async def find_one(self, model, query):
        from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
        from orion.services.mongo_manager.shared_model.db_message_model import db_message_model

        if model is db_mailbox_model:
            return self.mailbox
        if model is db_message_model:
            return self.message
        return self.keys.get(dict(query)["auth_id"]["$eq"])

    async def save(self, document):
        from orion.services.mongo_manager.shared_model.db_user_key_model import db_user_key_model

        if isinstance(document, db_user_key_model):
            self.keys[document.auth_id] = document
        else:
            self.saved_messages.append(document)
        return document


def build_encryption_stack(mailbox=None, message=None):
    from cryptography.fernet import Fernet

    from orion.services.encryption_manager.encryption_manager import encryption_manager
    from orion.services.encryption_manager.key_manager import key_manager
    from orion.services.encryption_manager.message_crypto_manager import message_crypto_manager

    engine = FakeKeyEngine(mailbox=mailbox, message=message)

    keys = object.__new__(key_manager)
    keys._engine = engine
    keys._master = encryption_manager.create(Fernet.generate_key())
    keys._private_key_cache = {}
    setattr(key_manager, "_key_manager__instance", keys)

    crypto = object.__new__(message_crypto_manager)
    crypto._engine = engine
    crypto._owner_cache = {}
    setattr(message_crypto_manager, "_message_crypto_manager__instance", crypto)

    return crypto, engine
