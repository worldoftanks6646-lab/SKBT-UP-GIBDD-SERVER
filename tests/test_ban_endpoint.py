from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_device_id
from app.main import app
from app.schemas.ban import ActiveBanResponse, BanListResponse, BanResponse
from app.services.ban_service import BanConflictError, BanPermissionDeniedError, BanService
from app.services.websocket_manager import chat_connections


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
    chat_id = uuid4()
    events = []

    async def issue(_db, received_witness_id, payload):
        assert received_witness_id == witness_id
        assert payload.issued_by_device_id == device_id
        assert payload.reason == "Repeated violation"
        return ban_response(witness_id, employee_id)

    async def witness_chat_id(_db, received_witness_id):
        assert received_witness_id == witness_id
        return chat_id

    async def broadcast(received_chat_id, event):
        assert received_chat_id == chat_id
        events.append(event)

    monkeypatch.setattr(BanService, "issue", issue)
    monkeypatch.setattr(BanService, "witness_chat_id", witness_chat_id)
    monkeypatch.setattr(chat_connections, "broadcast", broadcast)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/witnesses/{witness_id}/bans",
            json={
                "issued_by_device_id": str(device_id),
                "reason": "Repeated violation",
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["ban_level"] == 2
    assert events[0]["event"] == "observer_banned"
    assert events[0]["data"]["reason"] == "Repeated violation"
    assert events[0]["data"]["issued_at"].endswith("Z")


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


def test_ban_policy_uses_required_durations() -> None:
    now = datetime.now(timezone.utc)

    first_level, first_expiration = BanService._ban_policy(0, now)
    second_level, second_expiration = BanService._ban_policy(1, now)
    third_level, third_expiration = BanService._ban_policy(2, now)

    assert first_level == 1
    assert first_expiration == now + timedelta(days=1)
    assert second_level == 2
    assert second_expiration == now + timedelta(days=30)
    assert third_level == 3
    assert third_expiration is None


def test_witness_can_get_own_active_ban(monkeypatch) -> None:
    device_id = uuid4()
    issued_at = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
    expires_at = issued_at + timedelta(days=1)

    async def own_active_ban(_db, received_device_id):
        assert received_device_id == device_id
        return ActiveBanResponse(
            active=True,
            id=uuid4(),
            ban_level=1,
            issued_at=issued_at,
            expires_at=expires_at,
            reason="Violation",
        )

    monkeypatch.setattr(BanService, "own_active_ban", own_active_ban)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/witnesses/me/active-ban",
            params={"requester_device_id": str(device_id)},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["active"] is True
    assert response.json()["ban_level"] == 1
    assert response.json()["issued_at"] == "2026-08-25T10:00:00Z"
    assert response.json()["expires_at"] == "2026-08-26T10:00:00Z"


def test_no_active_ban_has_minimal_response(monkeypatch) -> None:
    device_id = uuid4()

    async def own_active_ban(_db, _device_id):
        return ActiveBanResponse(active=False)

    monkeypatch.setattr(BanService, "own_active_ban", own_active_ban)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/witnesses/me/active-ban",
            params={"requester_device_id": str(device_id)},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"active": False}


def test_witness_cannot_request_active_ban_for_another_device() -> None:
    claimed_device_id = uuid4()

    async def current_device():
        return uuid4()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_device_id] = current_device
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/witnesses/me/active-ban",
            params={"requester_device_id": str(claimed_device_id)},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_revoke_ban_broadcasts_websocket_event(monkeypatch) -> None:
    witness_id = uuid4()
    device_id = uuid4()
    chat_id = uuid4()
    result = ban_response(witness_id, uuid4())
    result.revoked_at = datetime.now(timezone.utc)
    events = []

    async def revoke(_db, received_witness_id, received_ban_id, payload):
        assert received_witness_id == witness_id
        assert received_ban_id == result.id
        assert payload.revoked_by_device_id == device_id
        return result

    async def witness_chat_id(_db, _witness_id):
        return chat_id

    async def broadcast(received_chat_id, event):
        assert received_chat_id == chat_id
        events.append(event)

    monkeypatch.setattr(BanService, "revoke", revoke)
    monkeypatch.setattr(BanService, "witness_chat_id", witness_chat_id)
    monkeypatch.setattr(chat_connections, "broadcast", broadcast)
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/witnesses/{witness_id}/bans/{result.id}/revoke",
            json={"revoked_by_device_id": str(device_id), "comment": "Reviewed"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert events[0]["event"] == "observer_ban_revoked"
    assert events[0]["data"]["revoked_at"].endswith("Z")
