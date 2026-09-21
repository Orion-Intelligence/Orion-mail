from pydantic import BaseModel, Field, field_validator

from orion.api.interactive.messenger_manager.messenger_enums import MESSENGER_LIMITS


class MessengerSendRequest(BaseModel):
    receiver_user_id: str
    body: str = Field(min_length=1, max_length=MESSENGER_LIMITS.BODY_MAX_LENGTH)

    @field_validator("receiver_user_id")
    @classmethod
    def normalize_receiver_user_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message body is required")

        return value
