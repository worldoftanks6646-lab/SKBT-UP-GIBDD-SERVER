from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.message import MessageSenderType, MessageType


class TextMessageCreate(BaseModel):
    sender_device_id: UUID
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_id: UUID
    sender_device_id: UUID
    sender_type: MessageSenderType
    message_type: MessageType
    text: str | None
    sent_at: datetime
    read_at: datetime | None
    deleted: bool


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    next_before: datetime | None = None
