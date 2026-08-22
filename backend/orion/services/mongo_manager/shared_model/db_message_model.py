from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import List, Optional

from odmantic import EmbeddedModel, Field, Model, ObjectId

from orion.services.mongo_manager.mongo_enums import MONGO_COLLECTIONS
from orion.services.mongo_manager.shared_model.db_attachment_model import ATTACHMENT_STATUS, STORAGE_TYPE


class MESSAGE_DIRECTION(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class MESSAGE_FOLDER(str, Enum):
    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    ARCHIVE = "archive"
    SPAM = "spam"
    TRASH = "trash"


class DELIVERY_STATUS(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    RECEIVED = "received"
    PARTIAL = "partial"
    BOUNCED = "bounced"
    FAILED = "failed"


class db_message_attachment(EmbeddedModel):
    id: str
    original_filename: str
    stored_filename: str
    size: int
    content_type: str = Field(default="application/octet-stream")
    storage_type: STORAGE_TYPE
    expires_at: datetime
    status: ATTACHMENT_STATUS = Field(default=ATTACHMENT_STATUS.AVAILABLE)
    content_id: Optional[str] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)


class db_message_model(Model):
    model_config = {"collection": MONGO_COLLECTIONS.MESSAGES, "parse_doc_with_default_factories": True}

    owner_mailbox_id: ObjectId = Field(index=True)
    sender_address: str
    receiver_address: str
    to_addresses: List[str] = Field(default_factory=list)
    cc_addresses: List[str] = Field(default_factory=list)
    bcc_addresses: List[str] = Field(default_factory=list)
    reply_to_address: Optional[str] = Field(default=None)
    subject: str
    body: str
    body_html: Optional[str] = Field(default=None)
    is_encrypted: bool = Field(default=False)
    sealed_key: Optional[str] = Field(default=None)
    attachments: List[db_message_attachment] = Field(default_factory=list)
    label_ids: List[ObjectId] = Field(default_factory=list)
    direction: MESSAGE_DIRECTION
    folder: MESSAGE_FOLDER
    previous_folder: Optional[MESSAGE_FOLDER] = Field(default=None)
    is_read: bool = Field(default=False)
    is_starred: bool = Field(default=False)
    is_important: bool = Field(default=False)
    snoozed_until: Optional[datetime] = Field(default=None)
    scheduled_at: Optional[datetime] = Field(default=None)
    delivery_status: DELIVERY_STATUS = Field(default=DELIVERY_STATUS.QUEUED)
    failed_recipients: List[str] = Field(default_factory=list)
    bounce_status: Optional[str] = Field(default=None)
    bounce_recipient: Optional[str] = Field(default=None)
    spf_result: Optional[str] = Field(default=None)
    dkim_result: Optional[str] = Field(default=None)
    dmarc_result: Optional[str] = Field(default=None)
    message_id_header: Optional[str] = Field(default=None)
    in_reply_to: Optional[str] = Field(default=None)
    references: List[str] = Field(default_factory=list)
    thread_id: Optional[ObjectId] = Field(default=None)
    forwarded_from_message_id: Optional[ObjectId] = Field(default=None)
    raw_source_filename: Optional[str] = Field(default=None)
    raw_source_encrypted: bool = Field(default=False)
    raw_source_size: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
