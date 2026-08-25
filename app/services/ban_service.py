from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import (
    Device,
    DeviceType,
    Employee,
    Chat,
    Role,
    RoleAssignment,
    NotificationType,
    Witness,
    WitnessBan,
)
from app.schemas.ban import ActiveBanResponse, BanCreateRequest, BanListResponse, BanResponse, BanRevokeRequest
from app.services.witness_access import witness_has_active_ban
from app.services.notification_service import NotificationService


class WitnessNotFoundError(ValueError):
    pass


class BanNotFoundError(ValueError):
    pass


class BanConflictError(ValueError):
    pass


class BanPermissionDeniedError(PermissionError):
    pass


class BanService:
    @staticmethod
    def _ban_policy(
        previous_ban_count: int, now: datetime
    ) -> tuple[int, datetime | None]:
        if previous_ban_count <= 0:
            return 1, now + timedelta(days=1)
        if previous_ban_count == 1:
            return 2, now + timedelta(days=30)
        return 3, None

    @staticmethod
    async def _require_ban_manager(db: AsyncSession, device_id: UUID) -> Employee:
        employee = await db.scalar(
            select(Employee)
            .join(Device, Device.id == Employee.device_id)
            .join(RoleAssignment, RoleAssignment.employee_id == Employee.id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .where(
                Device.id == device_id,
                Device.type == DeviceType.EMPLOYEE,
                RoleAssignment.revoked_at.is_(None),
            )
        )
        if employee is None:
            raise BanPermissionDeniedError(
                "Only employee with an active role can manage witness bans"
            )
        return employee

    @staticmethod
    async def issue(
        db: AsyncSession, witness_id: UUID, payload: BanCreateRequest
    ) -> BanResponse:
        manager = await BanService._require_ban_manager(
            db, payload.issued_by_device_id
        )
        witness = await db.get(Witness, witness_id)
        if witness is None:
            raise WitnessNotFoundError("Witness not found")
        active_ban = await db.scalar(
            select(WitnessBan).where(
                WitnessBan.witness_id == witness.id,
                WitnessBan.revoked_at.is_(None),
                or_(
                    WitnessBan.expires_at.is_(None),
                    WitnessBan.expires_at > func.now(),
                ),
            )
        )
        if active_ban is not None:
            raise BanConflictError("Witness already has an active ban")
        previous_ban_count = (
            await db.scalar(
                select(func.count(WitnessBan.id)).where(
                    WitnessBan.witness_id == witness.id
                )
            )
        ) or 0
        now = datetime.now(timezone.utc)
        ban_level, expires_at = BanService._ban_policy(previous_ban_count, now)

        ban = WitnessBan(
            witness_id=witness.id,
            ban_level=ban_level,
            reason=payload.reason,
            issued_by_employee_id=manager.id,
            expires_at=expires_at,
        )
        db.add(ban)
        witness.ban_level = ban_level
        witness.banned_at = now
        witness.ban_reason = payload.reason
        await db.flush()
        await NotificationService.notify_chiefs(
            db,
            NotificationType.BAN_ISSUED,
            "witness_ban",
            ban.id,
            {
                "witness_id": str(witness.id),
                "ban_level": ban_level,
                "reason": payload.reason,
            },
        )
        await db.commit()
        await db.refresh(ban)
        return BanResponse.model_validate(ban)

    @staticmethod
    async def history(
        db: AsyncSession, witness_id: UUID, requester_device_id: UUID
    ) -> BanListResponse:
        await BanService._require_ban_manager(db, requester_device_id)
        if await db.get(Witness, witness_id) is None:
            raise WitnessNotFoundError("Witness not found")
        bans = list(
            (
                await db.scalars(
                    select(WitnessBan)
                    .where(WitnessBan.witness_id == witness_id)
                    .order_by(WitnessBan.issued_at.desc())
                )
            ).all()
        )
        return BanListResponse(items=bans)

    @staticmethod
    async def own_active_ban(
        db: AsyncSession, requester_device_id: UUID
    ) -> ActiveBanResponse:
        witness = await db.scalar(
            select(Witness).where(Witness.device_id == requester_device_id)
        )
        if witness is None:
            raise BanPermissionDeniedError(
                "Only a witness can view its own active ban"
            )
        if not await witness_has_active_ban(db, witness):
            return ActiveBanResponse(active=False)
        ban = await db.scalar(
            select(WitnessBan)
            .where(
                WitnessBan.witness_id == witness.id,
                WitnessBan.revoked_at.is_(None),
                or_(
                    WitnessBan.expires_at.is_(None),
                    WitnessBan.expires_at > func.now(),
                ),
            )
            .order_by(WitnessBan.issued_at.desc())
            .limit(1)
        )
        if ban is None:
            return ActiveBanResponse(active=False)
        return ActiveBanResponse(
            active=True,
            id=ban.id,
            ban_level=ban.ban_level,
            issued_at=ban.issued_at,
            expires_at=ban.expires_at,
            reason=ban.reason,
        )

    @staticmethod
    async def witness_chat_id(db: AsyncSession, witness_id: UUID) -> UUID | None:
        return await db.scalar(select(Chat.id).where(Chat.witness_id == witness_id))

    @staticmethod
    async def revoke(
        db: AsyncSession, witness_id: UUID, ban_id: UUID, payload: BanRevokeRequest
    ) -> BanResponse:
        manager = await BanService._require_ban_manager(
            db, payload.revoked_by_device_id
        )
        witness = await db.get(Witness, witness_id)
        if witness is None:
            raise WitnessNotFoundError("Witness not found")
        ban = await db.get(WitnessBan, ban_id)
        if ban is None or ban.witness_id != witness.id:
            raise BanNotFoundError("Ban not found")
        if ban.revoked_at is not None:
            raise BanConflictError("Ban has already been revoked")

        ban.revoked_at = datetime.now(timezone.utc)
        ban.revoked_by_employee_id = manager.id
        ban.comment = payload.comment
        witness.ban_level = 0
        witness.banned_at = None
        witness.ban_reason = None
        await NotificationService.notify_chiefs(
            db,
            NotificationType.BAN_REVOKED,
            "witness_ban",
            ban.id,
            {"witness_id": str(witness.id)},
        )
        await db.commit()
        await db.refresh(ban)
        return BanResponse.model_validate(ban)
