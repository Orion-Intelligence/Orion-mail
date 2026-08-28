from datetime import UTC, datetime

from fastapi import HTTPException, status
from odmantic.exceptions import DuplicateKeyError
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.mailbox_manager.models.mailbox_param_model import MailboxCreateRequest
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_address_book_entry_model import db_address_book_entry_model
from orion.services.mongo_manager.shared_model.db_domain_safety_model import db_sender_block_model
from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class mailbox_manager:
    __instance = None
    LOCAL_TEST_USERNAMES = ("test1", "test2", "test3")

    @staticmethod
    def get_instance():
        if mailbox_manager.__instance is None:
            mailbox_manager()
        return mailbox_manager.__instance

    def __init__(self):
        if mailbox_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        mailbox_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    async def create_mailbox(self, current_user: db_user_model) -> dict:
        if await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == current_user.id) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has a mailbox")

        try:
            username = MailboxCreateRequest(username=current_user.username).username
        except ValidationError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Your Orion Intelligence username cannot be used as an email username") from error
        mailbox_address = f"{username}@{CONSTANTS.S_MAIL_DOMAIN}"
        try:
            mailbox = await self._engine.save(db_mailbox_model(user_id=current_user.id, mailbox_address=mailbox_address))
        except DuplicateKeyError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mailbox address already exists") from error

        return {"mailbox_address": mailbox.mailbox_address, "is_active": mailbox.is_active, "signature": mailbox.signature}

    async def seed_local_test_mailboxes(self) -> int:
        user_collection = self._engine.get_collection(db_user_model)
        mailbox_collection = self._engine.get_collection(db_mailbox_model)
        created_count = 0

        for username in self.LOCAL_TEST_USERNAMES:
            mailbox_address = f"{username}@{CONSTANTS.S_MAIL_DOMAIN}"
            mailbox = await mailbox_collection.find_one({"mailbox_address": mailbox_address})
            if mailbox is not None:
                if not mailbox.get("is_active", True):
                    await mailbox_collection.update_one({"_id": mailbox["_id"]}, {"$set": {"is_active": True, "updated_at": datetime.now(UTC)}})
                continue

            user = await user_collection.find_one({"email": mailbox_address})
            if user is None:
                now = datetime.now(UTC)
                await user_collection.update_one(
                    {"email": mailbox_address},
                    {"$setOnInsert": {"full_name": f"Test {username.removeprefix('test')}", "email": mailbox_address, "username": username, "created_at": now, "updated_at": now}},
                    upsert=True,
                )
                user = await user_collection.find_one({"email": mailbox_address})

            if user is None:
                continue
            user_id = user["_id"]

            if await mailbox_collection.find_one({"user_id": user_id}) is not None:
                continue

            now = datetime.now(UTC)
            try:
                await mailbox_collection.insert_one({"user_id": user_id, "mailbox_address": mailbox_address, "is_active": True, "created_at": now, "updated_at": now})
                created_count += 1
            except MongoDuplicateKeyError:
                continue

        return created_count

    async def get_user_mailbox(self, current_user: db_user_model) -> dict:
        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == current_user.id)

        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")

        return {"mailbox_address": mailbox.mailbox_address, "is_active": mailbox.is_active, "signature": mailbox.signature}

    async def update_mailbox_settings(self, current_user: db_user_model, signature: str) -> dict:
        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == current_user.id)

        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")

        mailbox.signature = signature.strip()
        mailbox.updated_at = datetime.now(UTC)
        await self._engine.save(mailbox)
        return {"mailbox_address": mailbox.mailbox_address, "signature": mailbox.signature}

    async def delete_mailbox(self, current_user: db_user_model) -> dict:
        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == current_user.id)

        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")

        messages = await self._engine.find(db_message_model, db_message_model.owner_mailbox_id == mailbox.id)
        for message in messages:
            await attachment_manager.get_instance().delete_message_attachments(message.id)
            await attachment_manager.get_instance().delete_raw_source(message.raw_source_filename)
            await self._engine.delete(message)

        await self._engine.get_collection(db_address_book_entry_model).delete_many({"owner_mailbox_id": mailbox.id})
        await self._engine.get_collection(db_label_model).delete_many({"user_id": current_user.id})
        await self._engine.get_collection(db_sender_block_model).delete_many({"user_id": current_user.id})
        await self._engine.delete(mailbox)
        return {"message": "Mailbox and all stored mail deleted"}

