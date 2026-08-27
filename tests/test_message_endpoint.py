from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.message import MessageSenderType, MessageType
from app.schemas.message import (
    MessageListResponse,
    MessageResponse,
    MessageTemplateListResponse,
    MessageTemplateResponse,
)
from app.services.message_service import ChatAccessDeniedError, MessageService
from app.services.push_service import PushService


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


def test_employee_can_send_regular_text_and_witness_gets_push(monkeypatch) -> None:
    chat_id = uuid4()
    sender_id = uuid4()
    item = message_response(chat_id, sender_id)
    item.sender_type = MessageSenderType.EMPLOYEE
    item.text = "Обычный ответ сотрудника"
    push_calls = []

    async def create_message(_db, received_chat_id, received_sender_id, text):
        assert received_chat_id == chat_id
        assert received_sender_id == sender_id
        assert text == "Обычный ответ сотрудника"
        return item

    async def notify_message(
        _db, received_chat_id, received_sender_id, sender_type, message_id, message_type
    ):
        push_calls.append(
            (received_chat_id, received_sender_id, sender_type, message_id, message_type)
        )

    monkeypatch.setattr(MessageService, "create_text_message", create_message)
    monkeypatch.setattr(PushService, "notify_chat_message", notify_message)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={
                "sender_device_id": str(sender_id),
                "text": "Обычный ответ сотрудника",
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["sender_type"] == "employee"
    assert push_calls == [(chat_id, sender_id, "employee", item.id, "text")]


def test_list_employee_templates(monkeypatch) -> None:
    device_id = uuid4()
    template_id = uuid4()

    async def list_templates(_db, received_device_id):
        assert received_device_id == device_id
        return MessageTemplateListResponse(
            items=[MessageTemplateResponse(id=template_id, code="accepted", text="Принято")]
        )

    monkeypatch.setattr(MessageService, "list_templates", list_templates)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/message-templates",
            params={"requester_device_id": str(device_id)},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(template_id)


def test_employee_sends_template(monkeypatch) -> None:
    chat_id = uuid4()
    sender_id = uuid4()
    template_id = uuid4()
    item = message_response(chat_id, sender_id)
    item.sender_type = MessageSenderType.EMPLOYEE
    push_calls = []

    async def create_template(_db, received_chat_id, received_sender_id, received_template_id):
        assert received_chat_id == chat_id
        assert received_sender_id == sender_id
        assert received_template_id == template_id
        return item

    async def notify_message(
        _db,
        received_chat_id,
        received_sender_id,
        sender_type,
        message_id,
        message_type,
    ):
        push_calls.append(
            (received_chat_id, received_sender_id, sender_type, message_id, message_type)
        )

    monkeypatch.setattr(MessageService, "create_template_message", create_template)
    monkeypatch.setattr(PushService, "notify_chat_message", notify_message)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{chat_id}/messages/template",
            json={"sender_device_id": str(sender_id), "template_id": str(template_id)},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["sender_type"] == "employee"
    assert push_calls == [(chat_id, sender_id, "employee", item.id, "text")]
