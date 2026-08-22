from __future__ import annotations

from datetime import UTC, datetime

from odmantic import Field, Model, ObjectId
from pydantic import field_validator

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_address_book_entry_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.ADDRESS_BOOK, "parse_doc_with_default_factories": True}

    owner_mailbox_id: ObjectId = Field(index=True)
    email_address: str
    use_count: int = Field(default=1, ge=1)
    first_used_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("email_address")
    @classmethod
    def normalize_email_address(cls, value: str) -> str:
        return value.strip().lower()
