from typing import Literal

from pydantic import BaseModel, Field, model_validator


LabelColor = Literal["#287fce", "#0f766e", "#7c3aed", "#c2410c", "#be123c", "#4d7c0f", "#475569", "#a16207"]


class LabelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: LabelColor = "#287fce"


class LabelUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: LabelColor | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.name is None and self.color is None:
            raise ValueError("At least one label field must be provided")
        return self
