from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import Witness, WitnessBan


async def witness_has_active_ban(db: AsyncSession, witness: Witness) -> bool:
    active_ban_id = await db.scalar(
        select(WitnessBan.id).where(
            WitnessBan.witness_id == witness.id,
            WitnessBan.revoked_at.is_(None),
            or_(WitnessBan.expires_at.is_(None), WitnessBan.expires_at > func.now()),
        )
    )
    if active_ban_id is not None:
        return True

    if witness.ban_level > 0:
        witness.ban_level = 0
        witness.banned_at = None
        witness.ban_reason = None
        await db.commit()
    return False
