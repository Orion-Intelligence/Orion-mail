from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from odmantic import Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS
from orion.services.mongo_manager.shared_model.model_fields import NormalizedDomain


class REPORT_TYPE(str, Enum):
    SPAM = "spam"
    PHISHING = "phishing"


class db_domain_report_model(Model):
    model_config = {
        "collection": MONGO_COLLECTIONS.DOMAIN_REPORTS,
        "parse_doc_with_default_factories": True,
    }

    reporter_user_id: ObjectId = Field(index=True)
    sender_domain: NormalizedDomain
    report_type: REPORT_TYPE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class db_domain_reputation_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.DOMAIN_REPUTATIONS, "parse_doc_with_default_factories": True}

    sender_domain: NormalizedDomain = Field(unique=True)
    spam_reports: int = Field(default=0, ge=0)
    phishing_reports: int = Field(default=0, ge=0)
    total_reports: int = Field(default=0, ge=0)
    user_block_count: int = Field(default=0, ge=0)
    is_blocked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class db_sender_block_model(Model):
    model_config = {
        "collection": MONGO_COLLECTIONS.SENDER_BLOCKS,
        "parse_doc_with_default_factories": True,
    }

    user_id: ObjectId = Field(index=True)
    sender_domain: NormalizedDomain
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
