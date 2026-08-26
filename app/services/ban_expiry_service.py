from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Witness, WitnessBan
from app.services.push_service import PushService


@dataclass(frozen=True)
class ExpiredBan:
    id: UUID
    device_id: UUID


class BanExpiryService:
    @staticmethod
    async def process(db: AsyncSession) -> int:
        now = datetime.now(timezone.utc)
        bans = list(
            (
                await db.scalars(
                    select(WitnessBan)
                    .where(
                        WitnessBan.revoked_at.is_(None),
                        WitnessBan.expires_at.is_not(None),
                        WitnessBan.expires_at <= now,
                        WitnessBan.expiry_notified_at.is_(None),
                    )
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        expired: list[ExpiredBan] = []
        for ban in bans:
            witness = await db.get(Witness, ban.witness_id)
            if witness is None:
                ban.expiry_notified_at = now
                continue
            active_ban_id = await db.scalar(
                select(WitnessBan.id).where(
                    WitnessBan.witness_id == witness.id,
                    WitnessBan.id != ban.id,
                    WitnessBan.is_active.is_(True),
                    WitnessBan.revoked_at.is_(None),
                    or_(
                        WitnessBan.expires_at.is_(None),
                        WitnessBan.expires_at > now,
                    ),
                )
            )
            ban.expiry_notified_at = now
            ban.is_active = False
            if active_ban_id is not None:
                continue
            witness.ban_level = 0
            witness.banned_at = None
            witness.ban_reason = None
            expired.append(ExpiredBan(id=ban.id, device_id=witness.device_id))

        await db.commit()
        for item in expired:
            await PushService.notify_device(
                db,
                item.device_id,
                "observer_ban_expired",
                "ГИБДД-Очевидец",
                "Срок блокировки завершён",
                {"ban_id": str(item.id)},
            )
        return len(expired)
