from __future__ import annotations

from datetime import UTC, datetime

from odmantic import Field, Model

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_user_key_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.USER_KEYS, "parse_doc_with_default_factories": True}

    auth_id: str = Field(unique=True)
    wrapped_key: str
    public_key: str
    wrapped_private_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
