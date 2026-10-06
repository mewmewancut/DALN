from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    conversation_token: str | None = Field(default=None, max_length=3000)

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Câu hỏi không được để trống")
        return value.strip()


class ChatPoll(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_token: str = Field(min_length=1, max_length=3000)


class ChatConfig(BaseModel):
    available: bool
    scope: str
    message: str


class ChatColumn(BaseModel):
    name: str
    type_name: str = "STRING"


class ChatTable(BaseModel):
    description: str
    columns: list[ChatColumn]
    rows: list[list[str | None]]
    truncated: bool


class ChatMessage(BaseModel):
    message_id: str
    conversation_token: str
    status: str
    text: str = ""
    tables: list[ChatTable] = Field(default_factory=list)
