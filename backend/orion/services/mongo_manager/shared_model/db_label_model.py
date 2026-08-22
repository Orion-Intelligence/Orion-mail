from __future__ import annotations

from datetime import UTC, datetime

from odmantic import Field, Model, ObjectId
from pydantic import field_validator

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_label_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.LABELS, "parse_doc_with_default_factories": True}

    user_id: ObjectId = Field(index=True)
    name: str
    normalized_name: str
    color: str = Field(default="#287fce")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("name", "normalized_name")
    @classmethod
    def strip_label_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.strip().lower()
