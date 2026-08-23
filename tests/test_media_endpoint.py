from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models import MediaType, MessageSenderType, MessageType
from app.schemas.media import AttachmentResponse, MediaMessageResponse
from app.schemas.message import MessageResponse
from app.services.media_service import MediaService, UnsupportedMediaTypeError
from app.services.message_service import ChatAccessDeniedError


async def override_db():
    yield object()


def media_response(chat_id, sender_id) -> MediaMessageResponse:
    now = datetime.now(timezone.utc)
    message_id = uuid4()
    attachment_id = uuid4()
    return MediaMessageResponse(
        message=MessageResponse(
            id=message_id,
            chat_id=chat_id,
            sender_device_id=sender_id,
            sender_type=MessageSenderType.WITNESS,
            message_type=MessageType.MEDIA,
            text=None,
            sent_at=now,
            read_at=None,
            deleted=False,
        ),
        attachment=AttachmentResponse(
            id=attachment_id,
            message_id=message_id,
            media_type=MediaType.PHOTO,
            mime_type="image/jpeg",
            original_name="photo.jpg",
            size_bytes=3,
            uploaded_at=now,
            expires_at=now + timedelta(days=7),
            download_url=f"/api/v1/media/{attachment_id}",
        ),
    )


def test_upload_media_returns_201(monkeypatch) -> None:
    chat_id = uuid4()
    sender_id = uuid4()

    async def upload(_db, received_chat_id, received_sender_id, file):
        assert received_chat_id == chat_id
        assert received_sender_id == sender_id
        assert file.content_type == "image/jpeg"
        return media_response(chat_id, sender_id)

    monkeypatch.setattr(MediaService, "upload", upload)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{chat_id}/media",
            data={"sender_device_id": str(sender_id)},
            files={"file": ("photo.jpg", b"jpg", "image/jpeg")},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["attachment"]["media_type"] == "photo"


def test_banned_witness_cannot_upload_media(monkeypatch) -> None:
    async def upload(_db, _chat_id, _sender_id, _file):
        raise ChatAccessDeniedError("Banned witness cannot access the chat")

    monkeypatch.setattr(MediaService, "upload", upload)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{uuid4()}/media",
            data={"sender_device_id": str(uuid4())},
            files={"file": ("photo.jpg", b"jpg", "image/jpeg")},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_unsupported_media_returns_400(monkeypatch) -> None:
    async def upload(_db, _chat_id, _sender_id, _file):
        raise UnsupportedMediaTypeError("Unsupported")

    monkeypatch.setattr(MediaService, "upload", upload)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/chats/{uuid4()}/media",
            data={"sender_device_id": str(uuid4())},
            files={"file": ("file.txt", b"text", "text/plain")},
        )
    finally:
        client.close()
        app.dependency_overrides.clear()

    assert response.status_code == 400
