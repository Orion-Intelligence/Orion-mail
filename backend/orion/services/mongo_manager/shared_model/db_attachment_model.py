from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class STORAGE_TYPE(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class ATTACHMENT_STATUS(str, Enum):
    AVAILABLE = "available"
    EXPIRED = "expired"


class db_attachment_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.ATTACHMENTS, "parse_doc_with_default_factories": True}

    message_id: ObjectId = Field(index=True)
    original_filename: str
    stored_filename: str
    size: int
    content_type: str = Field(default="application/octet-stream")
    storage_type: STORAGE_TYPE
    is_encrypted: bool = Field(default=False)
    expires_at: datetime
    status: ATTACHMENT_STATUS = Field(default=ATTACHMENT_STATUS.AVAILABLE)
    deleted_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
