from uuid import uuid4

import pytest

from app.services.websocket_manager import ChatConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


@pytest.mark.asyncio
async def test_chat_manager_broadcasts_only_to_selected_chat() -> None:
    manager = ChatConnectionManager()
    first_chat = uuid4()
    second_chat = uuid4()
    first_socket = FakeWebSocket()
    second_socket = FakeWebSocket()

    await manager.connect(first_chat, first_socket)
    await manager.connect(second_chat, second_socket)
    await manager.broadcast(first_chat, {"event": "message.created"})

    assert first_socket.accepted is True
    assert first_socket.messages == [{"event": "message.created"}]
    assert second_socket.messages == []

    manager.disconnect(first_chat, first_socket)
    await manager.broadcast(first_chat, {"event": "ignored"})
    assert len(first_socket.messages) == 1
