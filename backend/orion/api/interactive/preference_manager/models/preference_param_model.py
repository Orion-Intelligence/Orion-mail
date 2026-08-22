from typing import Literal

from pydantic import BaseModel


class UserPreferencesRequest(BaseModel):
    theme: Literal["light", "dark"]
