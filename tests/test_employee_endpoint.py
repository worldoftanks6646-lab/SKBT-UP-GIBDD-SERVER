from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_device_id
from app.main import app
from app.models.device import DeviceType
from app.models.role import RoleCode
from app.schemas.employee import DeviceListResponse, DeviceResponse, EmployeeResponse
from app.services.employee_service import EmployeeService


async def override_db():
    yield object()


def employee_response(device_id):
    now = datetime.now(timezone.utc)
    return EmployeeResponse(
        id=uuid4(),
        device_id=device_id,
        role=RoleCode.INSPECTOR,
        registered_at=now,
        last_activity_at=now,
    )


def device_response(device_id):
    now = datetime.now(timezone.utc)
    return DeviceResponse(
        id=device_id,
        type=DeviceType.EMPLOYEE,
        platform="android",
        app_version="1.0.0",
        registered_at=now,
        last_activity_at=now,
        employee_id=uuid4(),
        role=RoleCode.INSPECTOR,
    )


def test_current_employee_uses_authenticated_device(monkeypatch) -> None:
    device_id = uuid4()

    async def current_device():
        return device_id

    async def me(_db, received_device_id):
        assert received_device_id == device_id
        return employee_response(device_id)

    monkeypatch.setattr(EmployeeService, "me", me)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_device_id] = current_device
    with TestClient(app) as client:
        response = client.get("/api/v1/employee/me")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["device_id"] == str(device_id)


def test_compatibility_employee_device_list(monkeypatch) -> None:
    requester_id = uuid4()
    item = device_response(uuid4())

    async def list_devices(_db, received_id, limit, before, device_type):
        assert received_id == requester_id
        assert limit == 50
        assert before is None
        assert device_type == DeviceType.EMPLOYEE
        return DeviceListResponse(items=[item])

    monkeypatch.setattr(EmployeeService, "list_devices", list_devices)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/employee/devices",
            params={"requester_device_id": str(requester_id)},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["type"] == "employee"


def test_compatibility_specific_employee_device(monkeypatch) -> None:
    requester_id = uuid4()
    target_id = uuid4()

    async def get_device(_db, received_target, received_requester):
        assert received_target == target_id
        assert received_requester == requester_id
        return device_response(target_id)

    monkeypatch.setattr(EmployeeService, "get_device", get_device)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/employee/devices/{target_id}",
            params={"requester_device_id": str(requester_id)},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == str(target_id)


def test_device_response_does_not_expose_fingerprint() -> None:
    schema = app.openapi()["components"]["schemas"]["DeviceResponse"]

    assert "fingerprint_hash" not in schema["properties"]


def test_employee_compatibility_routes_are_in_openapi() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/employee/me" in paths
    assert "/api/v1/employee/devices" in paths
    assert "/api/v1/employee/devices/{device_id}" in paths
