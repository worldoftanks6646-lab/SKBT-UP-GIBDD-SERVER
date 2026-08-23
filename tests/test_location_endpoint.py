from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models import (
    LocationSessionStatus,
    LocationSessionType,
    MessageSenderType,
    MessageType,
)
from app.schemas.location import (
    LocationMessageResponse,
    LocationPointResponse,
    LocationSessionResponse,
)
from app.schemas.message import MessageResponse
from app.services.location_service import LocationService, LocationSessionStateError
from app.services.message_service import ChatAccessDeniedError


async def override_db():
    yield object()


def location_result(chat_id, sender_id, session_type) -> LocationMessageResponse:
    now = datetime.now(timezone.utc)
    message_id = uuid4()
    session_id = uuid4()
    point = LocationPointResponse(
        id=uuid4(), latitude=55.75, longitude=37.61, accuracy=5, captured_at=now, sequence_number=1
    )
    return LocationMessageResponse(
        message=MessageResponse(
            id=message_id,
            chat_id=chat_id,
            sender_device_id=sender_id,
            sender_type=MessageSenderType.WITNESS,
            message_type=MessageType.GEOLOCATION,
            text=None,
            sent_at=now,
            read_at=None,
            deleted=False,
            location_session_id=session_id,
        ),
        session=LocationSessionResponse(
            id=session_id,
            message_id=message_id,
            type=session_type,
            status=(LocationSessionStatus.FINISHED if session_type == LocationSessionType.STATIC else LocationSessionStatus.ACTIVE),
            started_at=now,
            expires_at=(None if session_type == LocationSessionType.STATIC else now + timedelta(minutes=15)),
            finished_at=(now if session_type == LocationSessionType.STATIC else None),
            points=([point] if session_type == LocationSessionType.STATIC else []),
        ),
    )


def test_create_static_location(monkeypatch) -> None:
    chat_id = uuid4()
    sender_id = uuid4()

    async def create(_db, received_chat_id, payload):
        assert received_chat_id == chat_id
        assert payload.sender_device_id == sender_id
        return location_result(chat_id, sender_id, LocationSessionType.STATIC)

    monkeypatch.setattr(LocationService, "create_static", create)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{chat_id}/locations/static",
            json={"sender_device_id": str(sender_id), "latitude": 55.75, "longitude": 37.61},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["session"]["type"] == "static"


def test_start_live_location(monkeypatch) -> None:
    chat_id = uuid4()
    sender_id = uuid4()

    async def start(_db, received_chat_id, payload):
        assert received_chat_id == chat_id
        assert payload.duration_seconds == 900
        return location_result(chat_id, sender_id, LocationSessionType.LIVE)

    monkeypatch.setattr(LocationService, "start_live", start)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{chat_id}/locations/live",
            json={"sender_device_id": str(sender_id), "duration_seconds": 900},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["session"]["status"] == "active"


def test_banned_witness_cannot_start_live(monkeypatch) -> None:
    async def start(_db, _chat_id, _payload):
        raise ChatAccessDeniedError("Banned witness cannot access the chat")

    monkeypatch.setattr(LocationService, "start_live", start)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{uuid4()}/locations/live",
            json={"sender_device_id": str(uuid4()), "duration_seconds": 900},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_expired_live_session_returns_409(monkeypatch) -> None:
    async def add(_db, _session_id, _payload):
        raise LocationSessionStateError("Location session has expired")

    monkeypatch.setattr(LocationService, "add_point", add)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/location-sessions/{uuid4()}/points",
            json={"sender_device_id": str(uuid4()), "latitude": 55.75, "longitude": 37.61},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 409
