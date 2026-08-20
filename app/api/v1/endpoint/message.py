from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.message import MessageListResponse, MessageResponse, TextMessageCreate
from app.services.message_service import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    DeviceNotFoundError,
    MessageNotFoundError,
    MessageService,
)
from app.services.websocket_manager import chat_connections


router = APIRouter(prefix="/chats", tags=["messages"])


def message_error_to_http(error: Exception) -> HTTPException:
    if isinstance(error, ChatAccessDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/{chat_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_text_message(
    chat_id: UUID,
    request: TextMessageCreate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        message = await MessageService.create_text_message(
            db, chat_id, request.sender_device_id, request.text
        )
        await chat_connections.broadcast(
            chat_id,
            {"event": "message.created", "data": message.model_dump(mode="json")},
        )
        return message
    except (ChatNotFoundError, DeviceNotFoundError, ChatAccessDeniedError) as error:
        raise message_error_to_http(error) from error


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def list_messages(
    chat_id: UUID,
    requester_device_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    try:
        return await MessageService.list_messages(
            db, chat_id, requester_device_id, limit, before
        )
    except (ChatNotFoundError, DeviceNotFoundError, ChatAccessDeniedError) as error:
        raise message_error_to_http(error) from error


@router.patch(
    "/{chat_id}/messages/{message_id}/read", response_model=MessageResponse
)
async def mark_message_as_read(
    chat_id: UUID,
    message_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        return await MessageService.mark_as_read(
            db, chat_id, message_id, requester_device_id
        )
    except (
        ChatNotFoundError,
        MessageNotFoundError,
        DeviceNotFoundError,
        ChatAccessDeniedError,
    ) as error:
        raise message_error_to_http(error) from error
