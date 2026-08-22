from __future__ import annotations

from datetime import UTC, datetime

from odmantic import Field, Model, ObjectId
from pydantic import field_validator

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_mailbox_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.MAILBOXES, "parse_doc_with_default_factories": True}

    user_id: ObjectId = Field(unique=True)
    mailbox_address: str = Field(unique=True)
    is_active: bool = Field(default=True)
    signature: str = Field(default="")
    address_book_backfilled_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("mailbox_address")
    @classmethod
    def normalize_mailbox_address(cls, value: str) -> str:
        return value.strip().lower()
