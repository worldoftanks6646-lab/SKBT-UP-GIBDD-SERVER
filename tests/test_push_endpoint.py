from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.schemas.push import PushTokenResponse
from app.services.push_service import PushDeviceNotFoundError, PushService


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
