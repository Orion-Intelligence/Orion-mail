from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class SHARED_FILE_STATUS(str, Enum):
    AVAILABLE = "available"
    DELETED = "deleted"
    UNAVAILABLE = "unavailable"


class db_shared_file_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.SHARED_FILES, "parse_doc_with_default_factories": True}

    owner_user_id: ObjectId = Field(index=True)

    public_id: str = Field(index=True)

    original_filename: str
    original_size: int
    content_type: str

    encrypted_size: int

    provider: str = Field(default="gofile")
    provider_content_id: str
    provider_filename: str
    provider_parent_folder: str
    provider_download_page: str
    provider_direct_url: str
    provider_guest_token: str

    encryption_algorithm: str = Field(default="AES-256-GCM")
    encryption_version: int = Field(default=1)
    iv: str

    status: SHARED_FILE_STATUS = Field(default=SHARED_FILE_STATUS.AVAILABLE)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
