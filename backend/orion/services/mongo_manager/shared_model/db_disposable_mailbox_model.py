from __future__ import annotations

from datetime import UTC, datetime

from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS
from orion.services.mongo_manager.shared_model.model_fields import NormalizedMailboxAddress, StrippedStr


class db_disposable_mailbox_model(Model):
    model_config = {
        "collection": MONGO_COLLECTIONS.DISPOSABLE_MAILBOXES,
        "parse_doc_with_default_factories": True,
    }

    user_id: ObjectId = Field(index=True)
    owner_mailbox_id: ObjectId = Field(index=True)
    mailbox_address: NormalizedMailboxAddress = Field(unique=True)
    pgp_key_id: ObjectId = Field(index=True)
    identity_signature: StrippedStr = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
