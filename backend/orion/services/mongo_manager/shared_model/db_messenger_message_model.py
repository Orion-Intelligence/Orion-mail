from __future__ import annotations
from datetime import UTC, datetime
from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_messenger_message_model(Model):
    model_config = { "collection": MONGO_COLLECTIONS.MESSENGER_MESSAGES, "parse_doc_with_default_factories": True}

    conversation_id: ObjectId = Field(index=True)

    sender_user_id: ObjectId = Field(index=True)
    receiver_user_id: ObjectId = Field(index=True)

    sender_mailbox_id: ObjectId = Field(index=True)
    receiver_mailbox_id: ObjectId = Field(index=True)

    encrypted_for_sender: str
    encrypted_for_receiver: str

    sender_key_fingerprint: str
    receiver_key_fingerprint: str

    read_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
