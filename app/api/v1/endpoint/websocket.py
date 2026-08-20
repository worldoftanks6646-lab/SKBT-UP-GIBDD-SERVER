from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.database import AsyncSessionLocal
from app.services.message_service import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    DeviceNotFoundError,
    MessageService,
)
from app.services.websocket_manager import chat_connections


router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/chats/{chat_id}")
async def chat_websocket(
    websocket: WebSocket, chat_id: UUID, device_id: UUID
) -> None:
    async with AsyncSessionLocal() as db:
        try:
            chat = await MessageService._get_chat(db, chat_id)
            await MessageService._authorize_device(db, chat, device_id)
        except ChatNotFoundError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        except (DeviceNotFoundError, ChatAccessDeniedError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await chat_connections.connect(chat_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chat_connections.disconnect(chat_id, websocket)
