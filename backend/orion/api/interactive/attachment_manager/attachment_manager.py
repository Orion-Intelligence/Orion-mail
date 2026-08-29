import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile, status
from fastapi.responses import Response
from odmantic.query import and_, eq, in_, lte

from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.api.server.config_manager.config_controller import config_controller
from orion.api.server.config_manager.config_enums import CONFIG_KEYS
from orion.constants.constant import CONSTANTS
from orion.services.antivirus_manager.antivirus_manager import antivirus_manager
from orion.services.encryption_manager.encryption_manager import encryption_manager
from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_attachment_model import ATTACHMENT_STATUS, STORAGE_TYPE, db_attachment_model
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_message_model import db_message_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class attachment_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if attachment_manager.__instance is None:
            attachment_manager()
        return attachment_manager.__instance

    def __init__(self):
        if attachment_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        attachment_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def get_storage_directory(storage_type: STORAGE_TYPE | str) -> Path:
        try:
            storage = STORAGE_TYPE(storage_type)
        except ValueError as error:
            raise ValueError("Invalid attachment storage type") from error
        directory = CONSTANTS.S_ATTACHMENT_DIR / storage.value
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def get_attachment_path(directory: Path, stored_filename: str) -> Path:
        storage_directory = directory.resolve()
        file_path = (storage_directory / stored_filename).resolve()
        if file_path.parent != storage_directory:
            raise ValueError("Invalid attachment path")
        return file_path

    @staticmethod
    def sanitize_original_filename(filename: str | None) -> str:
        cleaned = "".join(character for character in (filename or "attachment") if character >= " " and character != "\x7f").replace("\\", "_").strip()
        return (Path(cleaned).name or "attachment")[: MESSAGE_LIMITS.FILENAME_MAX_LENGTH]

    @staticmethod
    def generate_stored_filename(original_filename: str) -> str:
        suffix = Path(original_filename).suffix.lower()[: MESSAGE_LIMITS.SUFFIX_MAX_LENGTH]
        if not re.fullmatch(r"\.[a-z0-9]+", suffix):
            suffix = ""
        return f"{uuid4().hex}{suffix}"

    async def owner_cipher(self, owner_mailbox_id) -> encryption_manager | None:
        mailbox = await self._engine.find_one(db_mailbox_model, db_mailbox_model.id == owner_mailbox_id)
        if mailbox is None:
            return None
        return encryption_manager.create(await key_manager.get_instance().get_data_key(str(mailbox.user_id)))

    async def message_cipher(self, message_id: ObjectId) -> encryption_manager | None:
        message = await self._engine.find_one(db_message_model, db_message_model.id == message_id)
        return await self.owner_cipher(message.owner_mailbox_id) if message else None

    async def save_attachments(self, message_id: ObjectId, files: list[UploadFile], storage_type: STORAGE_TYPE, limit_key: str, limit_error: str, save_error: str) -> list[dict]:
        if not files:
            return []

        if len(files) > MESSAGE_LIMITS.MAX_ATTACHMENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A message cannot have more than {MESSAGE_LIMITS.MAX_ATTACHMENTS} attachments")

        limit_mb = await config_controller.get_instance().get_config_int(limit_key)
        retention_hours = await config_controller.get_instance().get_config_int(CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS)
        max_total_size = limit_mb * 1024 * 1024
        total_size = 0
        prepared_files = []

        for file in files:
            file_content = await file.read()
            await antivirus_manager.get_instance().assert_clean(file_content, self.sanitize_original_filename(file.filename))
            file_size = len(file_content)
            total_size += file_size
            if total_size > max_total_size:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=limit_error.format(limit_mb=limit_mb))
            prepared_files.append({"file": file, "content": file_content, "size": file_size})

        storage_directory = self.get_storage_directory(storage_type)
        expires_at = datetime.now(UTC) + timedelta(hours=retention_hours)
        cipher = await self.message_cipher(message_id)
        saved_attachments = []

        for prepared_file in prepared_files:
            file = prepared_file["file"]
            original_filename = self.sanitize_original_filename(file.filename)
            stored_filename = self.generate_stored_filename(original_filename)
            file_path = self.get_attachment_path(storage_directory, stored_filename)

            try:
                file_path.write_bytes(cipher.encrypt_bytes(prepared_file["content"]) if cipher else prepared_file["content"])
                attachment = await self._engine.save(db_attachment_model(message_id=message_id, original_filename=original_filename, stored_filename=stored_filename, size=prepared_file["size"], content_type=file.content_type or "application/octet-stream", storage_type=storage_type, expires_at=expires_at, is_encrypted=cipher is not None))
            except Exception as error:
                if file_path.exists():
                    file_path.unlink()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=save_error) from error

            saved_attachments.append({"id": str(attachment.id), "original_filename": attachment.original_filename, "stored_filename": attachment.stored_filename, "size": attachment.size, "content_type": attachment.content_type, "storage_type": storage_type.value, "expires_at": expires_at, "status": ATTACHMENT_STATUS.AVAILABLE.value})

        return saved_attachments

    async def save_incoming_attachments(self, message_id: ObjectId, files: list[UploadFile]) -> list[dict]:
        return await self.save_attachments(message_id, files, STORAGE_TYPE.INCOMING, CONFIG_KEYS.INCOMING_ATTACHMENT_MAX_SIZE_MB, "Total attachment size cannot exceed {limit_mb} MB", "Attachment could not be saved")

    async def outgoing_size_limit(self) -> tuple[int, int]:
        limit_mb = await config_controller.get_instance().get_config_int(CONFIG_KEYS.OUTGOING_ATTACHMENT_MAX_SIZE_MB)
        return limit_mb, limit_mb * 1024 * 1024

    @staticmethod
    def staging_directory() -> Path:
        return attachment_manager.get_storage_directory(STORAGE_TYPE.STAGING)

    @staticmethod
    def discard_staged_attachments(staged: list[dict]) -> None:
        directory = attachment_manager.staging_directory()
        for item in staged:
            try:
                file_path = attachment_manager.get_attachment_path(directory, item["stored_filename"])
                if file_path.is_file():
                    file_path.unlink()
            except (OSError, ValueError):
                continue

    async def stage_outgoing_attachments(self, files: list[UploadFile]) -> list[dict]:
        if not files:
            return []

        if len(files) > MESSAGE_LIMITS.MAX_ATTACHMENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A message cannot have more than {MESSAGE_LIMITS.MAX_ATTACHMENTS} attachments")

        limit_mb, max_total_size = await self.outgoing_size_limit()
        staging_directory = self.staging_directory()
        total_size = 0
        staged: list[dict] = []

        try:
            for file in files:
                file_content = await file.read()
                original_filename = self.sanitize_original_filename(file.filename)
                file_size = len(file_content)
                if file_size > max_total_size:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"{original_filename} is larger than the {limit_mb} MB attachment limit")
                total_size += file_size
                if total_size > max_total_size:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Total attachment size cannot exceed {limit_mb} MB")
                await antivirus_manager.get_instance().assert_clean(file_content, original_filename)
                stored_filename = self.generate_stored_filename(original_filename)
                staged.append({"original_filename": original_filename, "stored_filename": stored_filename, "size": file_size, "content_type": file.content_type or "application/octet-stream", "storage_type": STORAGE_TYPE.STAGING.value})
                self.get_attachment_path(staging_directory, stored_filename).write_bytes(file_content)
        except Exception:
            self.discard_staged_attachments(staged)
            raise

        return staged

    async def stage_forwarded_attachments(self, source_message_id: ObjectId, attachment_ids: list[str], staged: list[dict]) -> list[dict]:
        if not attachment_ids:
            return []

        try:
            object_ids = [ObjectId(attachment_id) for attachment_id in attachment_ids]
        except (InvalidId, TypeError) as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more forwarded attachment IDs are invalid") from error

        source_attachments = await self._engine.find(db_attachment_model, and_(eq(db_attachment_model.message_id, source_message_id), in_(db_attachment_model.id, object_ids), eq(db_attachment_model.status, ATTACHMENT_STATUS.AVAILABLE)))

        if len(source_attachments) != len(object_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more forwarded attachments are unavailable")

        if len(staged) + len(source_attachments) > MESSAGE_LIMITS.MAX_ATTACHMENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A message cannot have more than {MESSAGE_LIMITS.MAX_ATTACHMENTS} attachments")

        limit_mb, max_total_size = await self.outgoing_size_limit()
        staging_directory = self.staging_directory()
        total_size = sum(item["size"] for item in staged)
        forwarded: list[dict] = []

        try:
            for source_attachment in source_attachments:
                source_path = self.get_attachment_path(self.get_storage_directory(source_attachment.storage_type), source_attachment.stored_filename)
                if not source_path.is_file():
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more forwarded attachments are unavailable")

                source_bytes = source_path.read_bytes()
                if source_attachment.is_encrypted:
                    source_cipher = await self.message_cipher(source_attachment.message_id)
                    source_bytes = source_cipher.decrypt_bytes(source_bytes) if source_cipher else source_bytes

                total_size += len(source_bytes)
                if total_size > max_total_size:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Total attachment size cannot exceed {limit_mb} MB")

                stored_filename = self.generate_stored_filename(source_attachment.original_filename)
                forwarded.append({"original_filename": source_attachment.original_filename, "stored_filename": stored_filename, "size": len(source_bytes), "content_type": source_attachment.content_type, "storage_type": STORAGE_TYPE.STAGING.value})
                self.get_attachment_path(staging_directory, stored_filename).write_bytes(source_bytes)
        except Exception:
            self.discard_staged_attachments(forwarded)
            raise

        return forwarded

    @staticmethod
    def get_raw_source_path(stored_filename: str) -> Path:
        raw_directory = CONSTANTS.S_RAW_MESSAGE_DIR.resolve()
        raw_directory.mkdir(parents=True, exist_ok=True)
        file_path = (raw_directory / stored_filename).resolve()
        if file_path.parent != raw_directory:
            raise ValueError("Invalid raw message source path")
        return file_path

    async def save_raw_source(self, content: bytes, owner_mailbox_id=None) -> tuple[str, bool, int]:
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Raw message source is empty")
        if len(content) > MESSAGE_LIMITS.RAW_SOURCE_MAX_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Raw message source is too large")

        stored_filename = f"{uuid4().hex}.eml"
        file_path = self.get_raw_source_path(stored_filename)
        cipher = await self.owner_cipher(owner_mailbox_id) if owner_mailbox_id is not None else None
        try:
            file_path.write_bytes(cipher.encrypt_bytes(content) if cipher else content)
        except OSError as error:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Raw message source could not be stored") from error
        return stored_filename, cipher is not None, len(content)

    async def read_raw_source(self, message: db_message_model, source_path: Path) -> bytes:
        content = source_path.read_bytes()
        if not message.raw_source_encrypted:
            return content
        cipher = await self.owner_cipher(message.owner_mailbox_id)
        return cipher.decrypt_bytes(content) if cipher else content

    async def delete_raw_source(self, stored_filename: str | None) -> None:
        if not stored_filename:
            return
        try:
            file_path = self.get_raw_source_path(stored_filename)
        except ValueError:
            return
        if file_path.exists():
            file_path.unlink()

    async def delete_message_attachments(self, message_id: ObjectId) -> None:
        for attachment in await self._engine.find(db_attachment_model, db_attachment_model.message_id == message_id):
            file_path = self.get_storage_directory(attachment.storage_type) / attachment.stored_filename
            if file_path.exists():
                file_path.unlink()

        await self._engine.remove(db_attachment_model, db_attachment_model.message_id == message_id)

    async def cleanup_expired_attachments(self) -> dict:
        current_time = datetime.now(UTC)
        deleted_count = 0
        failed_count = 0

        for attachment in await self._engine.find(db_attachment_model, and_(eq(db_attachment_model.status, ATTACHMENT_STATUS.AVAILABLE), lte(db_attachment_model.expires_at, current_time))):
            try:
                file_path = self.get_storage_directory(attachment.storage_type) / attachment.stored_filename
                if file_path.exists():
                    file_path.unlink()
                attachment.status = ATTACHMENT_STATUS.EXPIRED
                attachment.deleted_at = current_time
                attachment.updated_at = current_time
                await self._engine.save(attachment)
                await self._engine.get_collection(db_message_model).update_one({"_id": attachment.message_id, "attachments.id": str(attachment.id)}, {"$set": {"attachments.$.status": ATTACHMENT_STATUS.EXPIRED.value, "attachments.$.deleted_at": current_time}})
                deleted_count += 1
            except Exception:
                failed_count += 1

        return {"deleted_count": deleted_count, "failed_count": failed_count}

    async def purge_expired_raw_sources(self) -> dict:
        retention_hours = await config_controller.get_instance().get_config_int(CONFIG_KEYS.ATTACHMENT_RETENTION_HOURS)
        cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
        collection = self._engine.get_collection(db_message_model)
        removed_count = 0
        failed_count = 0

        async for document in collection.find({"raw_source_filename": {"$ne": None}, "created_at": {"$lte": cutoff}}, {"_id": 1, "raw_source_filename": 1}):
            try:
                await self.delete_raw_source(document.get("raw_source_filename"))
                await collection.update_one({"_id": document["_id"]}, {"$set": {"raw_source_filename": None, "raw_source_encrypted": False, "raw_source_size": 0}})
                removed_count += 1
            except Exception:
                failed_count += 1

        return {"removed_count": removed_count, "failed_count": failed_count}

    async def purge_stale_staged_attachments(self) -> dict:
        directory = self.staging_directory()
        cutoff = datetime.now(UTC) - timedelta(seconds=CONSTANTS.S_OUTGOING_STAGING_TTL_SECONDS)
        removed_count = 0
        failed_count = 0

        for file_path in directory.iterdir():
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            try:
                if datetime.fromtimestamp(file_path.stat().st_mtime, UTC) > cutoff:
                    continue
                file_path.unlink()
                removed_count += 1
            except OSError:
                failed_count += 1

        return {"removed_count": removed_count, "failed_count": failed_count}

    async def download_attachment(self, attachment_id: str, current_user: db_user_model) -> Response:
        try:
            object_id = ObjectId(attachment_id)
        except InvalidId as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attachment ID") from error

        attachment = await self._engine.find_one(db_attachment_model, db_attachment_model.id == object_id)

        if attachment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

        message = await self._engine.find_one(db_message_model, db_message_model.id == attachment.message_id)

        if message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        mailbox = await self._engine.find_one(db_mailbox_model, and_(eq(db_mailbox_model.user_id, current_user.id), eq(db_mailbox_model.is_active, True)))

        if mailbox is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")

        if message.owner_mailbox_id != mailbox.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this attachment")

        if attachment.status != ATTACHMENT_STATUS.AVAILABLE:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Attachment is no longer available")

        storage_directory = CONSTANTS.S_ATTACHMENT_DIR / attachment.storage_type.value
        file_path = (storage_directory / attachment.stored_filename).resolve()

        if file_path.parent != storage_directory:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid attachment storage path")

        if not file_path.is_file():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Attachment file is no longer available")

        content = file_path.read_bytes()
        if attachment.is_encrypted:
            cipher = await self.owner_cipher(message.owner_mailbox_id)
            content = cipher.decrypt_bytes(content) if cipher else content

        return Response(content=content, media_type="application/octet-stream", headers={"X-Content-Type-Options": "nosniff", "Content-Disposition": 'attachment; filename="attachment"'})
