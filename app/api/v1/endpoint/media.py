from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.media import MediaMessageResponse
from app.services.media_service import (
    AttachmentNotFoundError,
    MediaFileError,
    MediaService,
    UnsupportedMediaTypeError,
)
from app.services.message_service import ChatAccessDeniedError, ChatNotFoundError, DeviceNotFoundError
from app.services.websocket_manager import chat_connections


router = APIRouter(tags=["media"])


@router.post("/chats/{chat_id}/media", response_model=MediaMessageResponse, status_code=201)
async def upload_media(
    chat_id: UUID,
    sender_device_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> MediaMessageResponse:
    try:
        result = await MediaService.upload(db, chat_id, sender_device_id, file)
        await chat_connections.broadcast(
            chat_id, {"event": "message.created", "data": result.message.model_dump(mode="json")}
        )
        return result
    except ChatAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (ChatNotFoundError, DeviceNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (UnsupportedMediaTypeError, MediaFileError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/media/{attachment_id}")
async def download_media(
    attachment_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    try:
        attachment, path = await MediaService.get_for_download(db, attachment_id, requester_device_id)
        return FileResponse(path, media_type=attachment.mime_type, filename=attachment.original_name)
    except ChatAccessDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (AttachmentNotFoundError, ChatNotFoundError, DeviceNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
