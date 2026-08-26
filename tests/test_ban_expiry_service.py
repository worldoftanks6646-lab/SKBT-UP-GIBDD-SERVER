from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.ban_expiry_service import BanExpiryService
from app.services.push_service import PushService


class ScalarRows:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


@pytest.mark.asyncio
async def test_expired_ban_clears_witness_and_sends_push(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    ban = SimpleNamespace(
        id=uuid4(),
        witness_id=uuid4(),
        expires_at=now - timedelta(minutes=1),
        expiry_notified_at=None,
    )
    witness = SimpleNamespace(
        id=ban.witness_id,
        device_id=uuid4(),
        ban_level=1,
        banned_at=now - timedelta(days=1),
        ban_reason="Violation",
    )
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=ScalarRows([ban])),
        get=AsyncMock(return_value=witness),
        scalar=AsyncMock(return_value=None),
        commit=AsyncMock(),
    )
    sent = []

    async def notify_device(_db, device_id, event, title, body, data):
        sent.append((device_id, event, title, body, data))

    monkeypatch.setattr(PushService, "notify_device", notify_device)

    processed = await BanExpiryService.process(db)

    assert processed == 1
    assert witness.ban_level == 0
    assert witness.banned_at is None
    assert witness.ban_reason is None
    assert ban.expiry_notified_at is not None
    assert sent[0][0] == witness.device_id
    assert sent[0][1] == "observer_ban_expired"
    assert sent[0][4] == {"ban_id": str(ban.id)}


@pytest.mark.asyncio
async def test_old_expired_ban_does_not_clear_new_active_ban(monkeypatch) -> None:
    ban = SimpleNamespace(
        id=uuid4(),
        witness_id=uuid4(),
        expiry_notified_at=None,
    )
    witness = SimpleNamespace(
        id=ban.witness_id,
        device_id=uuid4(),
        ban_level=2,
        banned_at=datetime.now(timezone.utc),
        ban_reason="New ban",
    )
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=ScalarRows([ban])),
        get=AsyncMock(return_value=witness),
        scalar=AsyncMock(return_value=uuid4()),
        commit=AsyncMock(),
    )
    notify = AsyncMock()
    monkeypatch.setattr(PushService, "notify_device", notify)

    processed = await BanExpiryService.process(db)

    assert processed == 0
    assert witness.ban_level == 2
    assert witness.ban_reason == "New ban"
    assert ban.expiry_notified_at is not None
    notify.assert_not_awaited()
