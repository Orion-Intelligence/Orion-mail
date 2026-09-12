from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from odmantic import ObjectId

from orion.api.interactive.address_book_manager.address_book_constants import ADDRESS_BOOK_LIMITS
from orion.api.interactive.address_book_manager.address_book_manager import address_book_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from tests.scripts.address_book_manager.fakes import FakeAddressCollection, FakeAddressEngine


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
