from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Optional

from odmantic import Field, Model
from pydantic import field_validator

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_user_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.USERS, "parse_doc_with_default_factories": True}

    full_name: str
    email: str = Field(unique=True)
    username: str = ""
    orion_user_id: str | None = None
    orion_tenant_id: str | None = None
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()
