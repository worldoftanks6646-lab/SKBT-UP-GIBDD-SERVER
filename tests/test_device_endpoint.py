from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.device import DeviceType
from app.schemas.device import DeviceRegisterResponse
from app.services.device_service import DeviceService, DeviceTypeConflictError


async def override_db():
    yield object()


def registration_payload() -> dict[str, str]:
    return {
        "fingerprint_hash": "a" * 64,
        "type": "witness",
        "platform": "android",
        "app_version": "1.0.0",
    }


def test_new_device_returns_201(monkeypatch) -> None:
    async def register_device(_db, _request):
        return DeviceRegisterResponse(
            device_id=uuid4(),
            type=DeviceType.WITNESS,
            is_new=True,
            witness_id=uuid4(),
            chat_id=uuid4(),
            ban_level=0,
        )

    monkeypatch.setattr(DeviceService, "register_device", register_device)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post("/api/v1/devices/register", json=registration_payload())
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["is_new"] is True


def test_existing_device_returns_200(monkeypatch) -> None:
    device_id = uuid4()

    async def register_device(_db, _request):
        return DeviceRegisterResponse(
            device_id=device_id,
            type=DeviceType.WITNESS,
            is_new=False,
            witness_id=uuid4(),
            chat_id=uuid4(),
            ban_level=0,
        )

    monkeypatch.setattr(DeviceService, "register_device", register_device)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post("/api/v1/devices/register", json=registration_payload())
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["device_id"] == str(device_id)
    assert response.json()["is_new"] is False


def test_device_type_change_returns_409(monkeypatch) -> None:
    async def register_device(_db, _request):
        raise DeviceTypeConflictError("An existing device cannot change its type")

    monkeypatch.setattr(DeviceService, "register_device", register_device)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post("/api/v1/devices/register", json=registration_payload())
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 409
