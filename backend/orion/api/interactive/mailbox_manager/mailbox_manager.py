from datetime import UTC, datetime
import re

from fastapi import HTTPException, status
from odmantic.exceptions import DuplicateKeyError
from odmantic.query import and_, eq
from pydantic import ValidationError

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.api.interactive.mailbox_manager.models.mailbox_param_model import MailboxCreateRequest
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_address_book_entry_model import db_address_book_entry_model
from orion.services.mongo_manager.shared_model.db_domain_safety_model import db_sender_block_model
from orion.services.mongo_manager.shared_model.db_label_model import db_label_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.api.interactive.disposable_mailbox_manager.disposable_mailbox_manager import disposable_mailbox_manager


class mailbox_manager:
    __instance = None
    LOCAL_TEST_USERNAMES = ("test1", "test2", "test3")
    LOCAL_UNCONFIGURED_USERNAME = "test4"

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

    @staticmethod
    def _resolve_mail_domain(current_user: db_user_model) -> str:
        return CONSTANTS.S_MAIL_DOMAIN

    async def create_mailbox(self, current_user: db_user_model) -> dict:
        if await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == current_user.id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has a mailbox"
            )

        try:
            username = MailboxCreateRequest(username=current_user.username).username
        except ValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Your Orion Intelligence username cannot be used as an email username"
            ) from error

        mail_domain = self._resolve_mail_domain(current_user)
        mailbox_address = f"{username}@{mail_domain}"

        try:
            mailbox = await self._engine.save(
                db_mailbox_model(user_id=current_user.id, mailbox_address=mailbox_address, mail_domain=mail_domain))
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mailbox address already exists"
            ) from error

        pgp_key = await disposable_mailbox_manager.get_instance().get_or_create_original_pgp(current_user, mailbox)

        return {
            "mailbox_address": mailbox.mailbox_address,
            "is_active": mailbox.is_active,
            "signature": mailbox.signature,
            "pgp_key_id": str(pgp_key.id),
            "fingerprint": pgp_key.fingerprint,
        }

    async def create_tenant_report_mailbox(self, tenant_id: str, tenant_slug: str, tenant_name: str) -> dict:
        tenant_id = str(tenant_id).strip()
        tenant_slug = str(tenant_slug).strip().lower()
        tenant_name = str(tenant_name).strip() or tenant_slug

        username = f"{tenant_slug}_report"
        try:
            username = MailboxCreateRequest(username=username).username
        except ValidationError:
            clean_slug = re.sub(r"[^a-z0-9]", "", tenant_slug)
            username = f"{clean_slug}_report"

        mail_domain = CONSTANTS.S_MAIL_DOMAIN
        mailbox_address = f"{username}@{mail_domain}"
        report_user_id = f"tenant_report_{tenant_id}"

        user = await self._engine.find_one(db_user_model, db_user_model.orion_user_id == report_user_id)
        if user is None:
            user = await self._engine.find_one(db_user_model, db_user_model.email == mailbox_address)
        if user is None:
            user = db_user_model(
                full_name=f"{tenant_name} Report Mail",
                email=mailbox_address,
                username=username,
                orion_user_id=report_user_id,
                orion_tenant_id=tenant_id,
                orion_tenant_slug=tenant_slug,
            )
            user = await self._engine.save(user)
        else:
            user.orion_user_id = report_user_id
            user.orion_tenant_id = tenant_id
            user.orion_tenant_slug = tenant_slug
            user.updated_at = datetime.now(UTC)
            user = await self._engine.save(user)

        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == user.id)
        if mailbox is None:
            mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.mailbox_address == mailbox_address)
        if mailbox is None:
            mailbox = await self._engine.save(
                db_mailbox_model(user_id=user.id, mailbox_address=mailbox_address, mail_domain=mail_domain)
            )

        pgp_key = await disposable_mailbox_manager.get_instance().get_or_create_original_pgp(user, mailbox)

        return {
            "mailbox_id": str(mailbox.id),
            "mailbox_address": mailbox.mailbox_address,
            "is_active": mailbox.is_active,
            "pgp_key_id": str(pgp_key.id) if pgp_key else None,
        }

    async def get_tenant_mailbox_status(self, tenant_id: str) -> dict:
        tenant_id = str(tenant_id).strip()
        report_user_id = f"tenant_report_{tenant_id}"
        user = await self._engine.find_one(db_user_model, db_user_model.orion_user_id == report_user_id)
        if user is None:
            return {
                "mailbox_exists": False,
                "keys_configured": False,
                "mailbox_address": None,
                "is_active": False,
            }
        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.user_id == user.id)
        if mailbox is None:
            return {
                "mailbox_exists": False,
                "keys_configured": False,
                "mailbox_address": None,
                "is_active": False,
            }
        e2e_key = await self._engine.find_one(
            db_pgp_key_model,
            and_(
                eq(db_pgp_key_model.owner_mailbox_id, mailbox.id),
                eq(db_pgp_key_model.key_type, PGP_KEY_TYPE.E2E),
            ),
        )
        keys_configured = e2e_key is not None
        return {
            "mailbox_exists": True,
            "keys_configured": keys_configured,
            "mailbox_address": mailbox.mailbox_address,
            "is_active": mailbox.is_active and keys_configured,
        }

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

            user_model = await self._engine.find_one(db_user_model, db_user_model.id == user_id)
            if user_model is None:
                continue
            try:
                await self.create_mailbox(user_model)
                created_count += 1
            except HTTPException:
                continue

        await self.seed_unconfigured_test_user()
        return created_count

    async def seed_unconfigured_test_user(self) -> None:
        username = self.LOCAL_UNCONFIGURED_USERNAME
        user_collection = self._engine.get_collection(db_user_model)
        email = f"{username}@{CONSTANTS.S_MAIL_DOMAIN}"
        now = datetime.now(UTC)
        await user_collection.update_one(
            {"email": email},
            {"$setOnInsert": {"full_name": f"Test {username.removeprefix('test')}", "email": email, "username": username, "created_at": now, "updated_at": now}},
            upsert=True,
        )

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
        await self._engine.get_collection(db_pgp_key_model).delete_many({"owner_mailbox_id": mailbox.id, "key_type": PGP_KEY_TYPE.E2E.value})
        await self._engine.delete(mailbox)
        return {"message": "Mailbox and all stored mail deleted"}

