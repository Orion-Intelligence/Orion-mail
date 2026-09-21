from pydantic import BaseModel, Field, field_validator


class MessengerSendRequest(BaseModel):
    receiver_user_id: str
    body: str = Field(min_length=1, max_length=5000)

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
