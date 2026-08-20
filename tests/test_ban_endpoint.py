from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.schemas.ban import BanListResponse, BanResponse
from app.services.ban_service import BanConflictError, BanPermissionDeniedError, BanService


async def override_db():
    yield object()


def ban_response(witness_id: UUID, employee_id: UUID) -> BanResponse:
    return BanResponse(
        id=uuid4(),
        witness_id=witness_id,
        ban_level=2,
        reason="Repeated violation",
        issued_by_employee_id=employee_id,
        issued_at=datetime.now(timezone.utc),
        expires_at=None,
        revoked_at=None,
        revoked_by_employee_id=None,
        comment=None,
    )


def test_chief_can_issue_ban(monkeypatch) -> None:
    witness_id = uuid4()
    device_id = uuid4()
    employee_id = uuid4()

    async def issue(_db, received_witness_id, payload):
        assert received_witness_id == witness_id
        assert payload.issued_by_device_id == device_id
        assert payload.ban_level == 2
        return ban_response(witness_id, employee_id)

    monkeypatch.setattr(BanService, "issue", issue)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/witnesses/{witness_id}/bans",
            json={
                "issued_by_device_id": str(device_id),
                "ban_level": 2,
                "reason": "Repeated violation",
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["ban_level"] == 2


def test_non_chief_cannot_issue_ban(monkeypatch) -> None:
    async def issue(_db, _witness_id, _payload):
        raise BanPermissionDeniedError("Only chief can manage witness bans")

    monkeypatch.setattr(BanService, "issue", issue)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/witnesses/{uuid4()}/bans",
            json={
                "issued_by_device_id": str(uuid4()),
                "ban_level": 1,
                "reason": "Violation",
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_second_active_ban_returns_conflict(monkeypatch) -> None:
    async def issue(_db, _witness_id, _payload):
        raise BanConflictError("Witness already has an active ban")

    monkeypatch.setattr(BanService, "issue", issue)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/witnesses/{uuid4()}/bans",
            json={
                "issued_by_device_id": str(uuid4()),
                "ban_level": 1,
                "reason": "Violation",
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 409


def test_chief_can_list_ban_history(monkeypatch) -> None:
    witness_id = uuid4()
    device_id = uuid4()
    item = ban_response(witness_id, uuid4())

    async def history(_db, received_witness_id, received_device_id):
        assert received_witness_id == witness_id
        assert received_device_id == device_id
        return BanListResponse(items=[item])

    monkeypatch.setattr(BanService, "history", history)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/witnesses/{witness_id}/bans",
            params={"requester_device_id": str(device_id)},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
