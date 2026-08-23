from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.attachment import MediaType
from app.schemas.message import MessageResponse


class AttachmentResponse(BaseModel):
    id: UUID
    message_id: UUID
    media_type: MediaType
    mime_type: str
    original_name: str
    size_bytes: int
    uploaded_at: datetime
    expires_at: datetime
    download_url: str


class MediaMessageResponse(BaseModel):
    message: MessageResponse
    attachment: AttachmentResponse
