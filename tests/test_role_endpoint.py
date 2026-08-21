from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.role import RoleCode
from app.schemas.role import RoleAssignmentResponse, RoleHistoryResponse
from app.services.role_service import RoleConflictError, RolePermissionDeniedError, RoleService


async def override_db():
    yield object()


def assignment_response(employee_id, role=RoleCode.INSPECTOR):
    return RoleAssignmentResponse(
        id=uuid4(),
        employee_id=employee_id,
        role=role,
        assigned_by_employee_id=uuid4(),
        assigned_at=datetime.now(timezone.utc),
        revoked_at=None,
    )


def test_manager_can_assign_role(monkeypatch) -> None:
    employee_id = uuid4()
    requester_id = uuid4()

    async def assign(_db, target_id, device_id, role):
        assert target_id == employee_id
        assert device_id == requester_id
        assert role == RoleCode.INSPECTOR
        return assignment_response(employee_id)

    monkeypatch.setattr(RoleService, "assign", assign)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/employees/{employee_id}/role",
            json={"requester_device_id": str(requester_id), "role": "inspector"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["role"] == "inspector"


def test_non_manager_cannot_assign_role(monkeypatch) -> None:
    async def assign(_db, _target_id, _device_id, _role):
        raise RolePermissionDeniedError("Not allowed")

    monkeypatch.setattr(RoleService, "assign", assign)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/employees/{uuid4()}/role",
            json={"requester_device_id": str(uuid4()), "role": "inspector"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_last_chief_cannot_be_revoked(monkeypatch) -> None:
    async def revoke(_db, _employee_id, _device_id):
        raise RoleConflictError("The last chief role cannot be revoked")

    monkeypatch.setattr(RoleService, "revoke", revoke)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.delete(
            f"/api/v1/employees/{uuid4()}/role",
            params={"requester_device_id": str(uuid4())},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 409


def test_manager_can_read_role_history(monkeypatch) -> None:
    employee_id = uuid4()
    requester_id = uuid4()

    async def history(_db, target_id, device_id):
        assert target_id == employee_id
        assert device_id == requester_id
        return RoleHistoryResponse(items=[assignment_response(employee_id)])

    monkeypatch.setattr(RoleService, "history", history)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/employees/{employee_id}/roles/history",
            params={"requester_device_id": str(requester_id)},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
