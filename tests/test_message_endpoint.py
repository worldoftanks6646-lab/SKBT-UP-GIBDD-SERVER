from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.message import MessageSenderType, MessageType
from app.schemas.message import MessageListResponse, MessageResponse
from app.services.message_service import ChatAccessDeniedError, MessageService


async def override_db():
    yield object()


def message_response(chat_id, sender_id) -> MessageResponse:
    return MessageResponse(
        id=uuid4(),
        chat_id=chat_id,
        sender_device_id=sender_id,
        sender_type=MessageSenderType.WITNESS,
        message_type=MessageType.TEXT,
        text="Сообщение",
        sent_at=datetime.now(timezone.utc),
        read_at=None,
        deleted=False,
    )


def test_create_text_message_returns_201(monkeypatch) -> None:
    chat_id = uuid4()
    sender_id = uuid4()

    async def create_message(_db, received_chat_id, received_sender_id, text):
        assert received_chat_id == chat_id
        assert received_sender_id == sender_id
        assert text == "Сообщение"
        return message_response(chat_id, sender_id)

    monkeypatch.setattr(MessageService, "create_text_message", create_message)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={"sender_device_id": str(sender_id), "text": "  Сообщение  "},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["message_type"] == "text"


def test_blank_text_is_rejected() -> None:
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{uuid4()}/messages",
            json={"sender_device_id": str(uuid4()), "text": "   "},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_list_messages_returns_paginated_response(monkeypatch) -> None:
    chat_id = uuid4()
    requester_id = uuid4()
    item = message_response(chat_id, requester_id)

    async def list_messages(_db, received_chat_id, received_requester_id, limit, before):
        assert received_chat_id == chat_id
        assert received_requester_id == requester_id
        assert limit == 20
        assert before is None
        return MessageListResponse(items=[item])

    monkeypatch.setattr(MessageService, "list_messages", list_messages)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/chats/{chat_id}/messages",
            params={"requester_device_id": str(requester_id), "limit": 20},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_access_denied_returns_403(monkeypatch) -> None:
    async def create_message(_db, _chat_id, _sender_id, _text):
        raise ChatAccessDeniedError("Device has no access to this chat")

    monkeypatch.setattr(MessageService, "create_text_message", create_message)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{uuid4()}/messages",
            json={"sender_device_id": str(uuid4()), "text": "Сообщение"},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_mark_message_as_read(monkeypatch) -> None:
    chat_id = uuid4()
    message_id = uuid4()
    requester_id = uuid4()
    item = message_response(chat_id, uuid4())
    item.read_at = datetime.now(timezone.utc)

    async def mark_as_read(_db, received_chat_id, received_message_id, received_id):
        assert received_chat_id == chat_id
        assert received_message_id == message_id
        assert received_id == requester_id
        return item

    monkeypatch.setattr(MessageService, "mark_as_read", mark_as_read)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.patch(
            f"/api/v1/chats/{chat_id}/messages/{message_id}/read",
            params={"requester_device_id": str(requester_id)},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["read_at"] is not None
