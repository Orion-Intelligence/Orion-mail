from __future__ import annotations

from datetime import UTC, datetime
from typing import Union

from odmantic import Field, Model

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS


class db_system_config_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.SYSTEM_CONFIG, "parse_doc_with_default_factories": True}

    key: str = Field(unique=True)
    value: Union[int, str]
    value_type: str = Field(default="integer")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
