from __future__ import annotations

from datetime import UTC, datetime

from odmantic import Field, Model, ObjectId
from pydantic import field_validator

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_disposable_mailbox_model(Model):
    model_config = {
        "collection": MONGO_COLLECTIONS.DISPOSABLE_MAILBOXES,
        "parse_doc_with_default_factories": True,
    }

    user_id: ObjectId = Field(index=True)
    owner_mailbox_id: ObjectId = Field(index=True)
    mailbox_address: str = Field(unique=True)
    pgp_key_id: ObjectId = Field(index=True)
    identity_signature: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("mailbox_address")
    @classmethod
    def normalize_mailbox_address(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("identity_signature")
    @classmethod
    def normalize_identity_signature(cls, value: str) -> str:
        return value.strip()