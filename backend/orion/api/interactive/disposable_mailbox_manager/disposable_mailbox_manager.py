import secrets
import string
from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from odmantic.query import and_, eq

from orion.api.interactive.attachment_manager.attachment_manager import attachment_manager
from orion.constants.constant import CONSTANTS
from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_disposable_mailbox_model import db_disposable_mailbox_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_STATUS, PGP_KEY_TYPE, db_pgp_key_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model
from orion.services.pgp_manager.pgp_manager import pgp_manager


class disposable_mailbox_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if disposable_mailbox_manager.__instance is None:
            disposable_mailbox_manager()
        return disposable_mailbox_manager.__instance

    def __init__(self):
        if disposable_mailbox_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        disposable_mailbox_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    async def get_owner_mailbox(self, current_user: db_user_model) -> db_mailbox_model:
        mailbox = await self._engine.find_one(
            db_mailbox_model,
            and_(eq(db_mailbox_model.user_id, current_user.id), eq(db_mailbox_model.is_active, True)),
        )
        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
        return mailbox

    async def active_disposable_count(self, current_user: db_user_model) -> int:
        return await self._engine.get_collection(db_disposable_mailbox_model).count_documents({"user_id": current_user.id})

    async def saved_pgp_count(self, current_user: db_user_model) -> int:
        return await self._engine.get_collection(db_pgp_key_model).count_documents({
            "user_id": current_user.id,
            "key_type": PGP_KEY_TYPE.DISPOSABLE.value,
            "status": PGP_KEY_STATUS.SAVED.value,
        })

    async def generate_random_address(self) -> str:
        alphabet = string.ascii_lowercase + string.digits

        for _ in range(20):
            local_part = "".join(secrets.choice(alphabet) for _ in range(CONSTANTS.S_RANDOM_MAILBOX_LENGTH))
            address = f"{local_part}@{CONSTANTS.S_MAIL_DOMAIN}".lower()
            exists = await self._engine.find_one(db_disposable_mailbox_model, db_disposable_mailbox_model.mailbox_address == address)
            if exists is None:
                return address

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate disposable address")

    async def create_pgp_key(self, current_user: db_user_model, mailbox: db_mailbox_model, key_type: PGP_KEY_TYPE) -> db_pgp_key_model:
        public_key, private_key, fingerprint = await pgp_manager.get_instance().generate_key_pair()
        record = db_pgp_key_model(
            user_id=current_user.id,
            owner_mailbox_id=mailbox.id,
            key_type=key_type,
            status=PGP_KEY_STATUS.ACTIVE,
            fingerprint=fingerprint,
            public_key=public_key,
            wrapped_private_key=key_manager.get_instance().wrap(private_key),
        )
        return await self._engine.save(record)

    async def get_or_create_original_pgp(self, current_user: db_user_model, mailbox: db_mailbox_model) -> db_pgp_key_model:
        existing = await self._engine.find_one(
            db_pgp_key_model,
            and_(
                eq(db_pgp_key_model.user_id, current_user.id),
                eq(db_pgp_key_model.owner_mailbox_id, mailbox.id),
                eq(db_pgp_key_model.key_type, PGP_KEY_TYPE.ORIGINAL),
            ),
        )
        return existing or await self.create_pgp_key(current_user, mailbox, PGP_KEY_TYPE.ORIGINAL)

    async def get_pgp_key(self, current_user: db_user_model, pgp_key_id: str) -> db_pgp_key_model:
        try:
            object_id = ObjectId(pgp_key_id)
        except InvalidId as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PGP key ID") from error

        key = await self._engine.find_one(
            db_pgp_key_model,
            and_(eq(db_pgp_key_model.id, object_id), eq(db_pgp_key_model.user_id, current_user.id)),
        )
        if key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PGP key not found")

        return key

    async def generate_disposable_mailbox(self, current_user: db_user_model, identity_signature: str, pgp_key_id: str | None = None) -> dict:
        mailbox = await self.get_owner_mailbox(current_user)

        identity_signature = self.validate_identity_signature(identity_signature)

        if await self.active_disposable_count(current_user) >= CONSTANTS.S_DISPOSABLE_MAILBOX_LIMIT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Disposable email limit reached")

        if pgp_key_id:
            pgp_key = await self.get_pgp_key(current_user, pgp_key_id)

            if pgp_key.key_type == PGP_KEY_TYPE.DISPOSABLE and pgp_key.status != PGP_KEY_STATUS.SAVED:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PGP key is not available")

            pgp_key.status = PGP_KEY_STATUS.ACTIVE
            pgp_key.updated_at = datetime.now(UTC)
            pgp_key = await self._engine.save(pgp_key)
        else:
            pgp_key = await self.create_pgp_key(current_user, mailbox, PGP_KEY_TYPE.DISPOSABLE)

        disposable = await self._engine.save(
            db_disposable_mailbox_model(
                user_id=current_user.id,
                owner_mailbox_id=mailbox.id,
                mailbox_address=await self.generate_random_address(),
                pgp_key_id=pgp_key.id,
                identity_signature=identity_signature,
            )
        )

        return {
            "type": "disposable",
            "id": str(disposable.id),
            "mailbox_address": disposable.mailbox_address,
            "pgp_key_id": str(pgp_key.id),
            "fingerprint": pgp_key.fingerprint,
            "identity_signature": disposable.identity_signature,
            "created_at": disposable.created_at,
        }

    async def list_sender_identities(self, current_user: db_user_model) -> dict:
        mailbox = await self.get_owner_mailbox(current_user)
        original_pgp = await self.get_or_create_original_pgp(current_user, mailbox)
        disposable = await self._engine.find(db_disposable_mailbox_model, db_disposable_mailbox_model.user_id == current_user.id)

        pgp_keys = await self._engine.find(
            db_pgp_key_model,
            db_pgp_key_model.user_id == current_user.id,
        )
        pgp_by_id = {key.id: key for key in pgp_keys}

        return {
            "original": {
                "type": "original",
                "id": str(mailbox.id),
                "mailbox_address": mailbox.mailbox_address,
                "pgp_key_id": str(original_pgp.id),
                "fingerprint": original_pgp.fingerprint,
            },
            "disposable": [
                {
                    "type": "disposable",
                    "id": str(item.id),
                    "mailbox_address": item.mailbox_address,
                    "pgp_key_id": str(item.pgp_key_id),
                    "fingerprint": pgp_by_id.get(item.pgp_key_id).fingerprint if pgp_by_id.get(item.pgp_key_id) else None,
                    "identity_signature": item.identity_signature,
                    "created_at": item.created_at,
                }
                for item in disposable
            ],
        }

    async def list_saved_pgp_keys(self, current_user: db_user_model) -> list[dict]:
        keys = await self._engine.find(
            db_pgp_key_model,
            and_(
                eq(db_pgp_key_model.user_id, current_user.id),
                eq(db_pgp_key_model.key_type, PGP_KEY_TYPE.DISPOSABLE),
                eq(db_pgp_key_model.status, PGP_KEY_STATUS.SAVED),
            ),
        )

        return [
            {
                "id": str(key.id),
                "fingerprint": key.fingerprint,
                "created_at": key.created_at,
            }
            for key in keys
        ]

    async def delete_disposable_mailbox(self, current_user: db_user_model, disposable_id: str, keep_pgp: bool) -> dict:
        try:
            object_id = ObjectId(disposable_id)
        except InvalidId as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid disposable email ID") from error

        disposable = await self._engine.find_one(
            db_disposable_mailbox_model,
            and_(eq(db_disposable_mailbox_model.id, object_id), eq(db_disposable_mailbox_model.user_id, current_user.id)),
        )
        if disposable is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disposable email not found")

        pgp_key = await self._engine.find_one(db_pgp_key_model, db_pgp_key_model.id == disposable.pgp_key_id)

        if (keep_pgp and pgp_key and pgp_key.key_type == PGP_KEY_TYPE.DISPOSABLE and await self.saved_pgp_count(current_user) >= CONSTANTS.S_SAVED_DISPOSABLE_PGP_LIMIT):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Saved PGP limit reached")

        messages = await self._engine.find(
            db_message_model,
            db_message_model.owner_mailbox_id == disposable.owner_mailbox_id,
        )

        for message in messages:
            if (
                message.sender_identity_id == disposable.id
                or message.sender_address == disposable.mailbox_address
                or message.receiver_address == disposable.mailbox_address
                or disposable.mailbox_address in message.to_addresses
                or disposable.mailbox_address in message.cc_addresses
                or disposable.mailbox_address in message.bcc_addresses
            ):
                await attachment_manager.get_instance().delete_message_attachments(message.id)
                await attachment_manager.get_instance().delete_raw_source(message.raw_source_filename)
                await self._engine.delete(message)

        await self._engine.delete(disposable)

        if pgp_key and pgp_key.key_type == PGP_KEY_TYPE.DISPOSABLE:
            if keep_pgp:
                pgp_key.status = PGP_KEY_STATUS.SAVED
                pgp_key.updated_at = datetime.now(UTC)
                await self._engine.save(pgp_key)
            else:
                await self._engine.delete(pgp_key)

        return {"message": "Disposable email deleted"}

    async def delete_saved_pgp_key(self, current_user: db_user_model, pgp_key_id: str) -> dict:
        key = await self.get_pgp_key(current_user, pgp_key_id)

        if key.key_type != PGP_KEY_TYPE.DISPOSABLE or key.status != PGP_KEY_STATUS.SAVED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only saved disposable PGP keys can be deleted")

        await self._engine.delete(key)
        return {"message": "Saved PGP key deleted"}

    @staticmethod
    def validate_identity_signature(identity_signature: str) -> str:
        value = identity_signature.strip()

        if not value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Disposable signature is required")

        if len(value) > 5000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Disposable signature cannot exceed 5000 characters")

        return value
