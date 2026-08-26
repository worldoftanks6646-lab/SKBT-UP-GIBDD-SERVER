from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChatListItem(BaseModel):
    id: UUID
    witness_id: UUID
    created_at: datetime
    last_message_at: datetime | None
    last_message_text: str | None
    unread_count: int
    is_banned: bool = False


class ChatListResponse(BaseModel):
    items: list[ChatListItem]
    next_before: datetime | None = None
