from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationSummary(BaseModel):
    id: int
    title: str
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    conversation_token: str | None
    can_resume: bool
    messages: list[dict]
    has_more: bool


class ConversationRename(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def trim(cls, value):
        if not value.strip():
            raise ValueError("Tên cuộc trò chuyện không được để trống")
        return value.strip()
