from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import (
    Device,
    DeviceType,
    Employee,
    Role,
    RoleAssignment,
    RoleCode,
    Witness,
    WitnessBan,
)
from app.schemas.ban import BanCreateRequest, BanListResponse, BanResponse, BanRevokeRequest


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
    async def _require_ban_manager(db: AsyncSession, device_id: UUID) -> Employee:
        employee = await db.scalar(
            select(Employee)
            .join(Device, Device.id == Employee.device_id)
            .join(RoleAssignment, RoleAssignment.employee_id == Employee.id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .where(
                Device.id == device_id,
                Device.type == DeviceType.EMPLOYEE,
                Role.code.in_([RoleCode.ADMINISTRATOR, RoleCode.CHIEF]),
                RoleAssignment.revoked_at.is_(None),
            )
        )
        if employee is None:
            raise BanPermissionDeniedError(
                "Only administrator or chief can manage witness bans"
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
        if payload.expires_at is not None and payload.expires_at <= datetime.now(timezone.utc):
            raise BanConflictError("Ban expiration must be in the future")

        ban = WitnessBan(
            witness_id=witness.id,
            ban_level=payload.ban_level,
            reason=payload.reason,
            issued_by_employee_id=manager.id,
            expires_at=payload.expires_at,
        )
        db.add(ban)
        witness.ban_level = payload.ban_level
        witness.banned_at = datetime.now(timezone.utc)
        witness.ban_reason = payload.reason
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
        await db.commit()
        await db.refresh(ban)
        return BanResponse.model_validate(ban)
