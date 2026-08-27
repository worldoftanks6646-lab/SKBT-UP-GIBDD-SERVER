from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.schemas.push import PushTokenResponse
from app.services.push_service import FcmClient, PushDeviceNotFoundError, PushService


async def override_db():
    yield object()


def test_device_can_register_push_token(monkeypatch) -> None:
    device_id = uuid4()
    token = "fcm-registration-token-value"

    async def register(_db, received_device_id, received_token):
        assert received_device_id == device_id
        assert received_token == token
        return PushTokenResponse(
            device_id=device_id,
            registered=True,
            updated_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(PushService, "register", register)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/devices/{device_id}/push-token",
            json={"token": token},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["registered"] is True
    assert "token" not in response.json()


def test_device_can_unregister_push_token(monkeypatch) -> None:
    device_id = uuid4()

    async def unregister(_db, received_device_id):
        assert received_device_id == device_id

    monkeypatch.setattr(PushService, "unregister", unregister)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.delete(f"/api/v1/devices/{device_id}/push-token")
    app.dependency_overrides.clear()

    assert response.status_code == 204


def test_unknown_device_push_token_is_rejected(monkeypatch) -> None:
    async def register(_db, _device_id, _token):
        raise PushDeviceNotFoundError("Device not found")

    monkeypatch.setattr(PushService, "register", register)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/devices/{uuid4()}/push-token",
            json={"token": "fcm-registration-token-value"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_short_push_token_is_rejected() -> None:
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/devices/{uuid4()}/push-token",
            json={"token": "short"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_notify_device_sends_only_to_its_registered_token(monkeypatch) -> None:
    device_id = uuid4()
    db = SimpleNamespace(scalar=AsyncMock(return_value="target-fcm-token-value"))
    sent = []

    monkeypatch.setattr(FcmClient, "configured", classmethod(lambda cls: True))

    async def send(_cls, tokens, title, body, data):
        sent.append((tokens, title, body, data))

    monkeypatch.setattr(FcmClient, "send", classmethod(send))

    await PushService.notify_device(
        db,
        device_id,
        "observer_banned",
        "Title",
        "Body",
        {"ban_id": "ban-id"},
    )

    assert sent == [
        (
            ["target-fcm-token-value"],
            "Title",
            "Body",
            {"event": "observer_banned", "ban_id": "ban-id"},
        )
    ]


@pytest.mark.asyncio
async def test_notify_device_without_token_does_not_send(monkeypatch) -> None:
    db = SimpleNamespace(scalar=AsyncMock(return_value=None))
    send = AsyncMock()
    monkeypatch.setattr(FcmClient, "configured", classmethod(lambda cls: True))
    monkeypatch.setattr(FcmClient, "send", send)

    await PushService.notify_device(
        db, uuid4(), "event", "Title", "Body"
    )

    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_employee_message_push_is_sent_only_to_chat_witness(monkeypatch) -> None:
    chat_id = uuid4()
    sender_device_id = uuid4()
    message_id = uuid4()
    db = SimpleNamespace(scalar=AsyncMock(return_value="witness-fcm-token-value"))
    sent = []

    monkeypatch.setattr(FcmClient, "configured", classmethod(lambda cls: True))

    async def send(_cls, tokens, title, body, data):
        sent.append((tokens, title, body, data))

    monkeypatch.setattr(FcmClient, "send", classmethod(send))

    await PushService.notify_chat_message(
        db,
        chat_id,
        sender_device_id,
        "employee",
        message_id,
        "text",
    )

    assert sent == [
        (
            ["witness-fcm-token-value"],
            "ГИБДД-Очевидец",
            "Новое сообщение",
            {
                "event": "message.created",
                "chat_id": str(chat_id),
                "message_id": str(message_id),
                "chat_message_type": "text",
            },
        )
    ]
    db.scalar.assert_awaited_once()
