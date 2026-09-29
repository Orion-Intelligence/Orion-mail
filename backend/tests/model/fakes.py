from __future__ import annotations

from typing import Any
import asyncio

from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS


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


class FakeMailboxEngine:
    def __init__(self):
        self.saved_mailbox = None

    @staticmethod
    async def find_one(*_args, **_kwargs):
        return None

    async def save(self, mailbox):
        self.saved_mailbox = mailbox
        return mailbox


class FakeCountingCollection:
    def __init__(self, count: int = 0):
        self._count = count
        self.delete_many_calls: list[Any] = []
        self.update_one_calls: list[Any] = []

    async def count_documents(self, _query):
        return self._count

    async def delete_many(self, query):
        self.delete_many_calls.append(query)
        return type("FakeDeleteResult", (), {"deleted_count": len(self.delete_many_calls)})()

    async def update_one(self, filter_query, update, **_kwargs):
        self.update_one_calls.append((filter_query, update))
        return type("FakeUpdateResult", (), {"modified_count": 1})()


class FakeEmailQuotaCollection:
    def __init__(self):
        self.document: dict | None = None
        self._lock = asyncio.Lock()

    async def update_one(self, filter_query, update, **kwargs):
        async with self._lock:

            if isinstance(update, dict):
                if self.document is None:
                    self.document = {**update.get("$setOnInsert", {}), **update.get("$set", {})}
                else:
                    self.document.update(update.get("$set", {}))

                return type(
                    "FakeUpdateResult",
                    (),
                    {"modified_count": 1},
                )()

            incoming = (
                update[0]["$set"]["recipients"]
                ["$filter"]["input"]["$map"]["in"]
                ["$cond"][0]["$in"][1]["$literal"]
            )

            counts = {
                item["address"]: item["count"]
                for item in self.document.get("recipients", [])
            }

            for address in incoming:
                if address in counts:
                    counts[address] -= 1

            self.document["recipients"] = [
                {
                    "address": address,
                    "count": count,
                }
                for address, count in counts.items()
                if count > 0
            ]

            return type(
                "FakeUpdateResult",
                (),
                {"modified_count": 1},
            )()

    async def find_one_and_update(self, filter_query, update_pipeline, **kwargs):
        async with self._lock:
            if self.document is None:
                return None

            incoming = (
                filter_query["$expr"]["$and"][0]
                ["$lte"][0]["$size"]["$setUnion"][1]["$literal"]
            )

            counts = {
                item["address"]: item["count"]
                for item in self.document.get("recipients", [])
            }

            for address in incoming:
                if (
                    counts.get(address, 0)
                    >= MESSAGE_LIMITS.MAX_DAILY_EMAILS_PER_RECIPIENT
                ):
                    return None

            total_unique = set(counts) | set(incoming)

            if (
                len(total_unique)
                > MESSAGE_LIMITS.MAX_DAILY_UNIQUE_RECIPIENTS
            ):
                return None

            for address in incoming:
                counts[address] = counts.get(address, 0) + 1

            self.document["recipients"] = [
                {
                    "address": address,
                    "count": count,
                }
                for address, count in counts.items()
            ]

            return self.document

    async def find_one(self, _filter):
        async with self._lock:
            return self.document

    def count_for(self, address: str) -> int:
        if self.document is None:
            return 0

        for item in self.document.get("recipients", []):
            if item["address"] == address:
                return item["count"]

        return 0

    def unique_recipient_count(self) -> int:
        if self.document is None:
            return 0

        return len(self.document.get("recipients", []))


class RecordingEngine:
    def __init__(self, find_one=None, find=None, counts=None, save_error=None, collections=None):
        self._find_one = find_one or {}
        self._find = find or {}
        self._counts = counts or {}
        self._save_error = save_error
        self.saved: list[Any] = []
        self.deleted: list[Any] = []
        self._collections: dict[Any, FakeCountingCollection] = {}
        self._provided_collections = collections or {}

    async def find_one(self, model, *_args, **_kwargs):
        behavior = self._find_one.get(model)
        if isinstance(behavior, list):
            return behavior.pop(0) if behavior else None
        return behavior

    async def find(self, model, *_args, **kwargs):
        results = self._find.get(model, [])
        limit = kwargs.get("limit")
        return list(results[:limit]) if limit is not None else list(results)

    async def save(self, document):
        if self._save_error is not None:
            raise self._save_error
        self.saved.append(document)
        return document

    async def delete(self, document):
        self.deleted.append(document)
        return document

    def get_collection(self, model):
        if model in self._provided_collections:
            return self._provided_collections[model]

        if model not in self._collections:
            self._collections[model] = FakeCountingCollection(self._counts.get(model, 0))

        return self._collections[model]


class FakePgpKey:
    def __init__(self):
        self.id = "pgpkey"
        self.fingerprint = "FINGERPRINT"


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
