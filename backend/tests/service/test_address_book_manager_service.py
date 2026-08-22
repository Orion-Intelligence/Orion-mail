import re
from datetime import UTC, datetime, timedelta

import pytest
from odmantic import ObjectId

from orion.api.interactive.address_book_manager.address_book_constants import ADDRESS_BOOK_LIMITS
from orion.api.interactive.address_book_manager.address_book_manager import address_book_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class FakeCursor:
    def __init__(self, entries):
        self.entries = list(entries)
        self.offset = 0
        self.maximum = None

    def sort(self, fields):
        field, direction = fields[0]
        self.entries.sort(key=lambda entry: entry[field], reverse=direction < 0)
        return self

    def skip(self, amount):
        self.offset = amount
        return self

    def limit(self, amount):
        self.maximum = amount
        return self

    async def to_list(self, length):
        maximum = self.maximum if self.maximum is not None else length
        entries = self.entries[self.offset:]
        return entries if maximum is None else entries[:maximum]


class FakeAddressCollection:
    def __init__(self, entries=None):
        self.entries = list(entries or [])

    async def update_one(self, query, update, upsert=False):
        entry = next((candidate for candidate in self.entries if candidate["owner_mailbox_id"] == query["owner_mailbox_id"] and candidate["email_address"] == query["email_address"]), None)
        if entry is None:
            if not upsert:
                return
            entry = dict(update["$setOnInsert"])
            entry["_id"] = ObjectId()
            entry["use_count"] = 0
            self.entries.append(entry)
        entry.update(update["$set"])
        entry["use_count"] += update["$inc"]["use_count"]

    def find(self, query, _projection=None):
        entries = [entry for entry in self.entries if entry["owner_mailbox_id"] == query["owner_mailbox_id"]]
        regex = query.get("email_address", {}).get("$regex")
        if regex:
            entries = [entry for entry in entries if re.search(regex, entry["email_address"])]
        return FakeCursor(entries)

    async def delete_many(self, query):
        stale_ids = set(query["_id"]["$in"])
        self.entries = [entry for entry in self.entries if entry["_id"] not in stale_ids]


class FakeAddressEngine:
    def __init__(self, mailbox, collection):
        self.mailbox = mailbox
        self.collection = collection

    async def find_one(self, *_args, **_kwargs):
        return self.mailbox

    def get_collection(self, _model):
        return self.collection


@pytest.mark.anyio
async def test_record_recipients_deduplicates_and_keeps_most_recent_1000():
    user = db_user_model(full_name="Admin", email="admin@orion.test", username="admin")
    mailbox = db_mailbox_model(user_id=user.id, mailbox_address="admin@mail.orion.test")
    old_time = datetime.now(UTC) - timedelta(days=30)
    entries = [
        {"_id": ObjectId(), "owner_mailbox_id": mailbox.id, "email_address": f"person{index:04d}@example.com", "use_count": 1, "first_used_at": old_time, "last_used_at": old_time + timedelta(seconds=index)}
        for index in range(ADDRESS_BOOK_LIMITS.MAX_ADDRESSES)
    ]
    collection = FakeAddressCollection(entries)
    manager = object.__new__(address_book_manager)
    manager._engine = FakeAddressEngine(mailbox, collection)

    await manager.record_recipients(mailbox, ["NEW@example.com", "new@example.com", "second@example.com"])

    assert len(collection.entries) == ADDRESS_BOOK_LIMITS.MAX_ADDRESSES
    assert {"new@example.com", "second@example.com"}.issubset({entry["email_address"] for entry in collection.entries})
    assert next(entry for entry in collection.entries if entry["email_address"] == "new@example.com")["use_count"] == 1


@pytest.mark.anyio
async def test_get_hints_is_mailbox_scoped_prefix_search_sorted_by_recency():
    user = db_user_model(full_name="Admin", email="admin@orion.test", username="admin")
    mailbox = db_mailbox_model(user_id=user.id, mailbox_address="admin@mail.orion.test")
    mailbox.address_book_backfilled_at = datetime.now(UTC)
    other_mailbox = db_mailbox_model(user_id=ObjectId(), mailbox_address="other@mail.orion.test")
    now = datetime.now(UTC)
    collection = FakeAddressCollection([
        {"_id": ObjectId(), "owner_mailbox_id": mailbox.id, "email_address": "alice@example.com", "use_count": 2, "first_used_at": now, "last_used_at": now - timedelta(hours=1)},
        {"_id": ObjectId(), "owner_mailbox_id": mailbox.id, "email_address": "alex@example.com", "use_count": 1, "first_used_at": now, "last_used_at": now},
        {"_id": ObjectId(), "owner_mailbox_id": other_mailbox.id, "email_address": "albert@example.com", "use_count": 9, "first_used_at": now, "last_used_at": now},
        {"_id": ObjectId(), "owner_mailbox_id": mailbox.id, "email_address": "bob@example.com", "use_count": 3, "first_used_at": now, "last_used_at": now},
    ])
    manager = object.__new__(address_book_manager)
    manager._engine = FakeAddressEngine(mailbox, collection)

    hints = await manager.get_hints(user, "al", limit=8)

    assert [hint["email_address"] for hint in hints] == ["alex@example.com", "alice@example.com"]
