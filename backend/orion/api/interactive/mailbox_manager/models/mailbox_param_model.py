import re
from typing import Optional

from pydantic import BaseModel, field_validator


MAILBOX_USERNAME_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$"
)


class MailboxCreateRequest(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not MAILBOX_USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Use 1–64 lowercase letters, numbers, dots, underscores, or hyphens"
            )
        return normalized

class TenantMailboxCreateRequest(BaseModel):
    tenant_id: str
    tenant_slug: str
    tenant_name: str


class TakedownSendRequest(BaseModel):
    tenant_id: str
    to_email: str
    subject: str
    target_domain: str
    custom_message: Optional[str] = ""
    html_content: Optional[str] = ""
    screenshot_base64: Optional[str] = ""
    screenshot_filename: Optional[str] = ""
    html_filename: Optional[str] = ""
    takedown_id: Optional[str] = ""
    body_html: Optional[str] = ""
    body_text: Optional[str] = ""

