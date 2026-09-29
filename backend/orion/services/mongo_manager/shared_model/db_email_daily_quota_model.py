from __future__ import annotations

from datetime import UTC, datetime
from typing import List

from odmantic import EmbeddedModel, Field, Model, ObjectId


class db_email_recipient_quota(EmbeddedModel):
    address: str
    count: int = Field(default=0, ge=0)


class db_email_daily_quota_model(Model):
    model_config = {"collection": "email_daily_quotas", "parse_doc_with_default_factories": True}
    owner_mailbox_id: ObjectId
    day_key: str
    recipients: List[db_email_recipient_quota] = Field(default_factory=list)
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
