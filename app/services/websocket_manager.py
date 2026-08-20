from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ChatConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, chat_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[chat_id].add(websocket)

    def disconnect(self, chat_id: UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(chat_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(chat_id, None)

    async def broadcast(self, chat_id: UUID, payload: dict) -> None:
        disconnected: list[WebSocket] = []
        for websocket in tuple(self._connections.get(chat_id, ())):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(chat_id, websocket)


chat_connections = ChatConnectionManager()
