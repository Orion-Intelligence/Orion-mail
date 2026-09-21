from __future__ import annotations
from datetime import UTC, datetime
from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS
from orion.services.mongo_manager.shared_model.model_fields import NormalizedMailboxAddress


class db_messenger_conversation_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.MESSENGER_CONVERSATIONS, "parse_doc_with_default_factories": True}

    conversation_key: str = Field(unique=True)

    user_a_id: ObjectId = Field(index=True)
    user_b_id: ObjectId = Field(index=True)

    user_a_mailbox_id: ObjectId = Field(index=True)
    user_b_mailbox_id: ObjectId = Field(index=True)

    user_a_address: NormalizedMailboxAddress
    user_b_address: NormalizedMailboxAddress

    last_message_id: ObjectId | None = Field(default=None)
    last_message_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
