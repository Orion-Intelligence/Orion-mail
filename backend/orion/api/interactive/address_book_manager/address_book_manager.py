import re
from datetime import UTC, datetime

from fastapi import HTTPException, status
from odmantic.query import and_, eq

from orion.api.interactive.address_book_manager.address_book_constants import ADDRESS_BOOK_LIMITS
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_address_book_entry_model import db_address_book_entry_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import DELIVERY_STATUS, MESSAGE_DIRECTION, MESSAGE_FOLDER, db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class address_book_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if address_book_manager.__instance is None:
            address_book_manager()
        return address_book_manager.__instance

    def __init__(self):
        if address_book_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        address_book_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    async def get_active_user_mailbox(self, current_user: db_user_model) -> db_mailbox_model:
        mailbox = await self._engine.find_one(db_mailbox_model, and_(eq(db_mailbox_model.user_id, current_user.id), eq(db_mailbox_model.is_active, True)))
        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
        return mailbox

    @staticmethod
    def normalized_addresses(addresses: list[str]) -> list[str]:
        return list(dict.fromkeys(address.strip().lower() for address in addresses if address.strip()))

    async def record_recipients(self, mailbox: db_mailbox_model, recipient_addresses: list[str]) -> None:
        addresses = self.normalized_addresses(recipient_addresses)
        if not addresses:
            return

        collection = self._engine.get_collection(db_address_book_entry_model)
        now = datetime.now(UTC)
        for email_address in addresses:
            await collection.update_one(
                {"owner_mailbox_id": mailbox.id, "email_address": email_address},
                {
                    "$set": {"last_used_at": now},
                    "$setOnInsert": {"owner_mailbox_id": mailbox.id, "email_address": email_address, "first_used_at": now},
                    "$inc": {"use_count": 1},
                },
                upsert=True,
            )

        await self.prune(mailbox.id)

    async def prune(self, mailbox_id) -> None:
        collection = self._engine.get_collection(db_address_book_entry_model)
        cursor = collection.find({"owner_mailbox_id": mailbox_id}, {"_id": 1}).sort([("last_used_at", -1), ("_id", -1)]).skip(ADDRESS_BOOK_LIMITS.MAX_ADDRESSES)
        stale_entries = await cursor.to_list(length=None)
        if stale_entries:
            await collection.delete_many({"_id": {"$in": [entry["_id"] for entry in stale_entries]}})

    async def backfill_from_sent_messages(self, mailbox: db_mailbox_model) -> None:
        if mailbox.address_book_backfilled_at is not None:
            return

        message_collection = self._engine.get_collection(db_message_model)
        pipeline = [
            {"$match": {"owner_mailbox_id": mailbox.id, "direction": MESSAGE_DIRECTION.OUTGOING.value, "folder": {"$ne": MESSAGE_FOLDER.DRAFTS.value}, "delivery_status": {"$ne": DELIVERY_STATUS.FAILED.value}}},
            {"$project": {"created_at": 1, "recipients": {"$setUnion": [{"$cond": [{"$gt": [{"$size": {"$ifNull": ["$to_addresses", []]}}, 0]}, {"$ifNull": ["$to_addresses", []]}, [{"$ifNull": ["$receiver_address", ""]}]]}, {"$ifNull": ["$cc_addresses", []]}]}}},
            {"$unwind": "$recipients"},
            {"$set": {"recipient": {"$toLower": {"$trim": {"input": "$recipients"}}}}},
            {"$match": {"recipient": {"$ne": ""}}},
            {"$group": {"_id": "$recipient", "use_count": {"$sum": 1}, "first_used_at": {"$min": "$created_at"}, "last_used_at": {"$max": "$created_at"}}},
            {"$sort": {"last_used_at": -1}},
            {"$limit": ADDRESS_BOOK_LIMITS.MAX_ADDRESSES},
        ]
        recipients = await message_collection.aggregate(pipeline).to_list(length=ADDRESS_BOOK_LIMITS.MAX_ADDRESSES)
        collection = self._engine.get_collection(db_address_book_entry_model)
        for recipient in recipients:
            await collection.update_one(
                {"owner_mailbox_id": mailbox.id, "email_address": recipient["_id"]},
                {
                    "$setOnInsert": {"owner_mailbox_id": mailbox.id, "email_address": recipient["_id"]},
                    "$min": {"first_used_at": recipient["first_used_at"]},
                    "$max": {"last_used_at": recipient["last_used_at"], "use_count": recipient["use_count"]},
                },
                upsert=True,
            )

        await self.prune(mailbox.id)
        backfilled_at = datetime.now(UTC)
        mailbox.address_book_backfilled_at = backfilled_at
        mailbox.updated_at = backfilled_at
        await self._engine.save(mailbox)

    async def get_hints(self, current_user: db_user_model, query: str, limit: int = ADDRESS_BOOK_LIMITS.DEFAULT_HINTS) -> list[dict]:
        mailbox = await self.get_active_user_mailbox(current_user)
        await self.backfill_from_sent_messages(mailbox)
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        collection = self._engine.get_collection(db_address_book_entry_model)
        cursor = collection.find({"owner_mailbox_id": mailbox.id, "email_address": {"$regex": f"^{re.escape(normalized_query)}"}}).sort([("last_used_at", -1), ("use_count", -1), ("email_address", 1)]).limit(limit)
        entries = await cursor.to_list(length=limit)
        return [{"email_address": entry["email_address"], "use_count": entry.get("use_count", 1), "last_used_at": entry["last_used_at"]} for entry in entries]
