from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class PGP_KEY_TYPE(str, Enum):
    ORIGINAL = "original"
    DISPOSABLE = "disposable"
    E2E = "e2e"


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
    recovery_private_key: Optional[str] = Field(default=None)
    kdf_salt: Optional[str] = Field(default=None)
    verifier_hash: Optional[str] = Field(default=None)
    recovery_verifier_hash: Optional[str] = Field(default=None)
    failed_unlocks: int = Field(default=0, ge=0)
    unlock_blocked_until: Optional[datetime] = Field(default=None)
    tab_secret: Optional[str] = Field(default=None)
    tab_secret_binding: Optional[str] = Field(default=None)
    tab_secret_expires_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))