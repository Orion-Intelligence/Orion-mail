from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AddressHintResponse(BaseModel):
    email_address: EmailStr
    use_count: int = Field(ge=1)
    last_used_at: datetime
