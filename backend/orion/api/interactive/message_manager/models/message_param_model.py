from enum import Enum
from typing import Annotated

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from orion.api.interactive.message_manager.message_enums import MESSAGE_LIMITS
from orion.services.mongo_manager.shared_model.db_domain_safety_model import REPORT_TYPE
from orion.services.mongo_manager.shared_model.db_message_model import MESSAGE_FOLDER


class SendMessageRequest(BaseModel):
    receiver_address: EmailStr
    subject: str = Field(max_length=255)
    body: str


class DraftMessageRequest(BaseModel):
    receiver_address: str = Field(default="", max_length=320)
    cc_addresses: list[Annotated[str, Field(max_length=320)]] = Field(default_factory=list, max_length=50)
    bcc_addresses: list[Annotated[str, Field(max_length=320)]] = Field(default_factory=list, max_length=50)
    subject: str = Field(default="", max_length=MESSAGE_LIMITS.SUBJECT_MAX_LENGTH)
    body: str = Field(default="", max_length=MESSAGE_LIMITS.BODY_MAX_LENGTH)
    body_html: str = Field(default="", max_length=MESSAGE_LIMITS.BODY_MAX_LENGTH)


class MessageLabelUpdateRequest(BaseModel):
    label_ids: list[str] = Field(default_factory=list, max_length=20)


class MessageMoveRequest(BaseModel):
    destination: MESSAGE_FOLDER


class MailboxSettingsRequest(BaseModel):
    signature: str = Field(default="", max_length=10000)


class ScheduleSendRequest(BaseModel):
    scheduled_at: datetime


class SnoozeRequest(BaseModel):
    snoozed_until: datetime


class SenderReportRequest(BaseModel):
    report_type: REPORT_TYPE


class MessageTranslationRequest(BaseModel):
    target_language: str = Field(min_length=2, max_length=10, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?$")


class MESSAGE_SEARCH_SCOPE(str, Enum):
    ALL = "all"
    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    ARCHIVE = "archive"
    SPAM = "spam"
    TRASH = "trash"
    STARRED = "starred"
    IMPORTANT = "important"
    LABEL = "label"


class BULK_MESSAGE_ACTION(str, Enum):
    ARCHIVE = "archive"
    TRASH = "trash"
    RESTORE = "restore"
    PERMANENT_DELETE = "permanent_delete"
    MARK_READ = "mark_read"
    MARK_UNREAD = "mark_unread"
    STAR = "star"
    UNSTAR = "unstar"
    MARK_IMPORTANT = "mark_important"
    MARK_NOT_IMPORTANT = "mark_not_important"
    MOVE = "move"
    ADD_LABELS = "add_labels"
    REPORT_SPAM = "report_spam"
    REPORT_PHISHING = "report_phishing"


class MessageBulkActionRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=100)
    action: BULK_MESSAGE_ACTION
    destination: MESSAGE_FOLDER | None = None
    label_ids: list[str] = Field(default_factory=list, max_length=20)
