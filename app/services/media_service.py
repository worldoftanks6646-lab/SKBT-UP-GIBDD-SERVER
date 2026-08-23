import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Attachment, DeviceType, MediaType, Message, MessageSenderType, MessageType
from app.schemas.media import AttachmentResponse, MediaMessageResponse
from app.schemas.message import MessageResponse
from app.services.message_service import MessageService


class UnsupportedMediaTypeError(ValueError):
    pass


class MediaFileError(ValueError):
    pass


class AttachmentNotFoundError(ValueError):
    pass


MIME_TYPES = {
    "image/jpeg": (MediaType.PHOTO, ".jpg"),
    "image/png": (MediaType.PHOTO, ".png"),
    "image/gif": (MediaType.GIF, ".gif"),
    "video/mp4": (MediaType.VIDEO, ".mp4"),
    "video/quicktime": (MediaType.VIDEO, ".mov"),
}


class MediaService:
    @staticmethod
    async def upload(
        db: AsyncSession, chat_id: UUID, sender_device_id: UUID, file: UploadFile
    ) -> MediaMessageResponse:
        chat = await MessageService._get_chat(db, chat_id)
        sender = await MessageService._authorize_device(db, chat, sender_device_id)
        media = MIME_TYPES.get(file.content_type or "")
        if media is None:
            raise UnsupportedMediaTypeError("Only JPEG, PNG, GIF, MP4 and MOV are allowed")

        media_type, extension = media
        storage_key = f"{uuid.uuid4().hex}{extension}"
        media_root = Path(settings.MEDIA_ROOT).resolve()
        media_root.mkdir(parents=True, exist_ok=True)
        final_path = media_root / storage_key
        temporary_path = media_root / f".{storage_key}.upload"
        size = 0
        try:
            with temporary_path.open("wb") as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.MEDIA_MAX_SIZE_BYTES:
                        raise MediaFileError("Media file is too large")
                    target.write(chunk)
            if size == 0:
                raise MediaFileError("Media file is empty")
            os.replace(temporary_path, final_path)

            message = Message(
                chat_id=chat.id,
                sender_device_id=sender.id,
                sender_type=(MessageSenderType.WITNESS if sender.type == DeviceType.WITNESS else MessageSenderType.EMPLOYEE),
                message_type=MessageType.MEDIA,
            )
            db.add(message)
            await db.flush()
            expires_at = datetime.now(timezone.utc) + timedelta(days=settings.MEDIA_TTL_DAYS)
            attachment = Attachment(
                message_id=message.id,
                media_type=media_type,
                mime_type=file.content_type,
                original_name=(file.filename or "media").replace("\\", "/").split("/")[-1],
                storage_key=storage_key,
                size_bytes=size,
                expires_at=expires_at,
            )
            db.add(attachment)
            chat.last_message_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(message)
            await db.refresh(attachment)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            if final_path.exists():
                final_path.unlink()
            await db.rollback()
            raise
        finally:
            await file.close()

        return MediaMessageResponse(
            message=MessageResponse.model_validate(message).model_copy(
                update={"attachment_id": attachment.id}
            ),
            attachment=AttachmentResponse(
                id=attachment.id,
                message_id=attachment.message_id,
                media_type=attachment.media_type,
                mime_type=attachment.mime_type,
                original_name=attachment.original_name,
                size_bytes=attachment.size_bytes,
                uploaded_at=attachment.uploaded_at,
                expires_at=attachment.expires_at,
                download_url=f"/api/v1/media/{attachment.id}",
            ),
        )

    @staticmethod
    async def get_for_download(db: AsyncSession, attachment_id: UUID, requester_device_id: UUID) -> tuple[Attachment, Path]:
        attachment = await db.get(Attachment, attachment_id)
        if attachment is None or attachment.deleted_at is not None:
            raise AttachmentNotFoundError("Attachment not found")
        message = await db.get(Message, attachment.message_id)
        if message is None or message.deleted:
            raise AttachmentNotFoundError("Attachment not found")
        chat = await MessageService._get_chat(db, message.chat_id)
        await MessageService._authorize_device(db, chat, requester_device_id)
        now = datetime.now(timezone.utc)
        if attachment.expires_at <= now:
            raise AttachmentNotFoundError("Attachment has expired")
        path = Path(settings.MEDIA_ROOT).resolve() / attachment.storage_key
        if not path.is_file():
            raise AttachmentNotFoundError("Attachment file not found")
        attachment.last_viewed_at = now
        attachment.expires_at = now + timedelta(days=settings.MEDIA_TTL_DAYS)
        await db.commit()
        return attachment, path
