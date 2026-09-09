from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class PGP_KEY_TYPE(str, Enum):
    ORIGINAL = "original"
    DISPOSABLE = "disposable"


class PGP_KEY_STATUS(str, Enum):
    ACTIVE = "active"
    SAVED = "saved"


class db_pgp_key_model(Model):
    model_config = {
        "collection": MONGO_COLLECTIONS.PGP_KEYS,
        "parse_doc_with_default_factories": True,
    }

    user_id: ObjectId = Field(index=True)
    owner_mailbox_id: ObjectId = Field(index=True)
    key_type: PGP_KEY_TYPE
    status: PGP_KEY_STATUS = Field(default=PGP_KEY_STATUS.ACTIVE)

    fingerprint: str = Field(unique=True)
    public_key: str
    wrapped_private_key: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))