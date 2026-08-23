from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models import NotificationType
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services.notification_service import NotificationService


async def override_db():
    yield object()


def notification_response(is_read: bool = False) -> NotificationResponse:
    return NotificationResponse(
        id=uuid4(),
        type=NotificationType.BAN_ISSUED,
        related_entity_type="witness_ban",
        related_entity_id=uuid4(),
        payload={"ban_level": 1},
        is_read=is_read,
        created_at=datetime.now(timezone.utc),
        read_at=datetime.now(timezone.utc) if is_read else None,
    )


def test_list_notifications(monkeypatch) -> None:
    device_id = uuid4()
    item = notification_response()

    async def list_items(_db, received_id, limit, before, unread_only):
        assert received_id == device_id
        assert limit == 20
        assert before is None
        assert unread_only is True
        return NotificationListResponse(items=[item])

    monkeypatch.setattr(NotificationService, "list_for_employee", list_items)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/notifications",
            params={"requester_device_id": str(device_id), "limit": 20, "unread_only": True},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["type"] == "ban_issued"


def test_mark_notification_read(monkeypatch) -> None:
    device_id = uuid4()
    notification_id = uuid4()
    item = notification_response(is_read=True)

    async def mark_read(_db, received_notification_id, received_device_id):
        assert received_notification_id == notification_id
        assert received_device_id == device_id
        return item

    monkeypatch.setattr(NotificationService, "mark_read", mark_read)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.patch(
            f"/api/v1/notifications/{notification_id}/read",
            json={"requester_device_id": str(device_id)},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["is_read"] is True
