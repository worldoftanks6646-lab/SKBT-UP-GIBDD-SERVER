from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.schemas.chat import ChatListItem, ChatListResponse
from app.services.chat_service import ChatService, EmployeeRoleRequiredError


async def override_db():
    yield object()


def test_employee_can_list_chats(monkeypatch) -> None:
    requester_id = uuid4()
    chat_id = uuid4()
    now = datetime.now(timezone.utc)

    async def list_chats(_db, received_id, limit, before):
        assert received_id == requester_id
        assert limit == 20
        assert before is None
        return ChatListResponse(
            items=[
                ChatListItem(
                    id=chat_id,
                    witness_id=uuid4(),
                    created_at=now,
                    last_message_at=now,
                    last_message_text="Проверка",
                    unread_count=2,
                )
            ]
        )

    monkeypatch.setattr(ChatService, "list_for_employee", list_chats)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/chats",
            params={"requester_device_id": str(requester_id), "limit": 20},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(chat_id)
    assert response.json()["items"][0]["unread_count"] == 2


def test_employee_without_role_cannot_list_chats(monkeypatch) -> None:
    async def list_chats(_db, _requester_id, _limit, _before):
        raise EmployeeRoleRequiredError("Employee has no assigned role")

    monkeypatch.setattr(ChatService, "list_for_employee", list_chats)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/chats",
            params={"requester_device_id": str(uuid4())},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 403
