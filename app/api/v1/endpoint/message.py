from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.schemas.message import (
    MessageListResponse,
    MessageResponse,
    MessageTemplateListResponse,
    TemplateMessageCreate,
    TextMessageCreate,
)
from app.services.message_service import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    DeviceNotFoundError,
    MessageNotFoundError,
    MessageTemplateNotFoundError,
    MessageService,
)
from app.services.websocket_manager import chat_connections
from app.services.push_service import PushService


router = APIRouter(prefix="/chats", tags=["messages"])
template_router = APIRouter(prefix="/message-templates", tags=["message templates"])


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
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> MessageResponse:
    verify_device_id(authenticated_device_id, request.sender_device_id)
    try:
        message = await MessageService.create_text_message(
            db, chat_id, request.sender_device_id, request.text
        )
        await PushService.notify_chat_message(
            db, chat_id, request.sender_device_id, message.id, message.message_type.value
        )
        await chat_connections.broadcast(
            chat_id,
            {"event": "message.created", "data": message.model_dump(mode="json")},
        )
        return message
    except (ChatNotFoundError, DeviceNotFoundError, ChatAccessDeniedError) as error:
        raise message_error_to_http(error) from error


@router.post(
    "/{chat_id}/messages/template",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_message(
    chat_id: UUID,
    request: TemplateMessageCreate,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> MessageResponse:
    verify_device_id(authenticated_device_id, request.sender_device_id)
    try:
        message = await MessageService.create_template_message(
            db, chat_id, request.sender_device_id, request.template_id
        )
        await PushService.notify_chat_message(
            db, chat_id, request.sender_device_id, message.id, message.message_type.value
        )
        await chat_connections.broadcast(
            chat_id,
            {"event": "message.created", "data": message.model_dump(mode="json")},
        )
        return message
    except (
        ChatNotFoundError,
        DeviceNotFoundError,
        ChatAccessDeniedError,
        MessageTemplateNotFoundError,
    ) as error:
        raise message_error_to_http(error) from error


@template_router.get("", response_model=MessageTemplateListResponse)
async def list_message_templates(
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> MessageTemplateListResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await MessageService.list_templates(db, requester_device_id)
    except (DeviceNotFoundError, ChatAccessDeniedError) as error:
        raise message_error_to_http(error) from error


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def list_messages(
    chat_id: UUID,
    requester_device_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> MessageListResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
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
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> MessageResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
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
