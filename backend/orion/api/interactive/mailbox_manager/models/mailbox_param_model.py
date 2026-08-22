import re

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
