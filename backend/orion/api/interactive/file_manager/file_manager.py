from __future__ import annotations

import base64
import secrets

from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile, status
from odmantic.query import and_, desc, eq

from orion.services.file_storage_manager.gofile_client import gofile_client
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_shared_file_model import SHARED_FILE_STATUS, db_shared_file_model
from orion.services.mongo_manager.shared_model.db_user_model import db_user_model


class file_manager:
    __instance = None

    MAX_FILE_BYTES = 100 * 1024 * 1024
    MAX_FILENAME_LENGTH = 255

    @staticmethod
    def get_instance():
        if file_manager.__instance is None:
            file_manager()

        return file_manager.__instance

    def __init__(self):
        if file_manager.__instance is not None:
            raise Exception("This class is a singleton!")

        file_manager.__instance = self

        self._engine = (
            mongo_controller
            .get_instance()
            .get_engine()
        )

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        cleaned = "".join(
            char
            for char in filename
            if char >= " " and char != "\x7f"
        )

        cleaned = cleaned.replace("\\", "_").strip()

        return (
            Path(cleaned).name
            or "file"
        )[:file_manager.MAX_FILENAME_LENGTH]

    @staticmethod
    def validate_iv(iv: str) -> None:
        try:
            padding = "=" * (-len(iv) % 4)

            decoded = base64.urlsafe_b64decode(
                iv + padding
            )

        except Exception as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid encryption IV") from error

        if len(decoded) != 12:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AES-GCM IV must be 12 bytes")

    @staticmethod
    def serialize_file(shared_file: db_shared_file_model) -> dict:
        return {
            "id": str(shared_file.id),
            "public_id": shared_file.public_id,
            "original_filename": shared_file.original_filename,
            "original_size": shared_file.original_size,
            "content_type": shared_file.content_type,
            "status": shared_file.status.value,
            "created_at": shared_file.created_at,
        }

    @staticmethod
    def serialize_public_file(shared_file: db_shared_file_model) -> dict:
        return {
            "public_id": shared_file.public_id,
            "original_filename": shared_file.original_filename,
            "original_size": shared_file.original_size,
            "encrypted_size": shared_file.encrypted_size,
            "content_type": shared_file.content_type,
            "iv": shared_file.iv,
            "encryption_algorithm": shared_file.encryption_algorithm,
            "encryption_version": shared_file.encryption_version,

            "provider_direct_url": (
                shared_file.provider_direct_url
            ),

            "content_url": (
                f"/api/files/public/"
                f"{shared_file.public_id}/content"
            ),
        }

    async def upload_file(self, current_user: db_user_model, encrypted_file: UploadFile, original_filename: str, original_size: int, content_type: str, iv: str) -> dict:

        if original_size < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid original file size")

        if original_size > self.MAX_FILE_BYTES:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File cannot exceed 100 MB")

        self.validate_iv(iv)

        filename = self.sanitize_filename(original_filename)

        mime_type = (content_type.strip()[:200] or "application/octet-stream")

        ciphertext = await encrypted_file.read()

        expected_encrypted_size = original_size + 16

        if len(ciphertext) != expected_encrypted_size:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Encrypted file size is invalid")

        provider_filename = (f"{secrets.token_hex(20)}.orion")

        provider = await gofile_client.upload(content=ciphertext, filename=provider_filename)

        shared_file = db_shared_file_model(
            owner_user_id=current_user.id,
            public_id=secrets.token_urlsafe(24),

            original_filename=filename,
            original_size=original_size,
            content_type=mime_type,
            encrypted_size=len(ciphertext),

            provider="gofile",
            provider_content_id=provider["content_id"],
            provider_filename=provider["filename"],
            provider_parent_folder=provider["parent_folder"],
            provider_download_page=provider["download_page"],
            provider_direct_url=provider["direct_url"],
            provider_guest_token=provider["guest_token"],

            iv=iv,
        )

        try:
            shared_file = await self._engine.save(
                shared_file
            )

        except Exception:
            await gofile_client.delete(content_id=provider["content_id"], guest_token=provider["guest_token"])
            raise

        return self.serialize_file(shared_file)

    async def get_my_files(self, current_user: db_user_model) -> list[dict]:

        files = await self._engine.find(
            db_shared_file_model,
            and_(
                eq(
                    db_shared_file_model.owner_user_id,
                    current_user.id,
                ),
                eq(
                    db_shared_file_model.status,
                    SHARED_FILE_STATUS.AVAILABLE,
                ),
            ),
            sort=desc(
                db_shared_file_model.created_at
            ),
        )

        return [
            self.serialize_file(item)
            for item in files
        ]

    async def get_public_file(self, public_id: str) -> db_shared_file_model:

        shared_file = await self._engine.find_one(
            db_shared_file_model,
            eq(
                db_shared_file_model.public_id,
                public_id,
            ),
        )

        if shared_file is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared file not found")

        if (
            shared_file.status
            != SHARED_FILE_STATUS.AVAILABLE
        ):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Shared file is no longer available")

        return shared_file

    async def get_public_metadata(self, public_id: str) -> dict:

        shared_file = await self.get_public_file(public_id)

        return self.serialize_public_file(shared_file)

    async def get_ciphertext(self, public_id: str) -> bytes:

        shared_file = await self.get_public_file(public_id)

        return await gofile_client.download(
            direct_url=shared_file.provider_direct_url,
            guest_token=shared_file.provider_guest_token,
            expected_size=shared_file.encrypted_size,
        )

    async def delete_file(self, current_user: db_user_model, file_id: str) -> dict:

        try:
            object_id = ObjectId(file_id)

        except InvalidId as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file ID") from error

        shared_file = await self._engine.find_one(
            db_shared_file_model,
            and_(
                eq(
                    db_shared_file_model.id,
                    object_id,
                ),
                eq(
                    db_shared_file_model.owner_user_id,
                    current_user.id,
                ),
            ),
        )

        if shared_file is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        await gofile_client.delete(content_id=shared_file.provider_content_id, guest_token=shared_file.provider_guest_token)

        shared_file.status = (SHARED_FILE_STATUS.DELETED)

        shared_file.updated_at = datetime.now(UTC)

        await self._engine.save(shared_file)

        return {
            "message": "File deleted",
        }
