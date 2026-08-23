from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Device,
    Employee,
    NotificationType,
    Role,
    RoleAssignment,
    RoleCode,
)
from app.schemas.role import RoleAssignmentResponse, RoleHistoryResponse
from app.services.notification_service import NotificationService


class EmployeeNotFoundError(ValueError):
    pass


class RolePermissionDeniedError(PermissionError):
    pass


class RoleConflictError(ValueError):
    pass


class RoleService:
    @staticmethod
    async def _chief_count(db: AsyncSession) -> int:
        return (
            await db.scalar(
                select(func.count(RoleAssignment.id))
                .join(Role, Role.id == RoleAssignment.role_id)
                .where(
                    RoleAssignment.revoked_at.is_(None),
                    Role.code == RoleCode.CHIEF,
                )
            )
        ) or 0

    @staticmethod
    async def _active_assignment(
        db: AsyncSession, employee_id: UUID
    ) -> RoleAssignment | None:
        return await db.scalar(
            select(RoleAssignment).where(
                RoleAssignment.employee_id == employee_id,
                RoleAssignment.revoked_at.is_(None),
            )
        )

    @staticmethod
    async def _requester(
        db: AsyncSession, device_id: UUID
    ) -> tuple[Employee, RoleCode]:
        row = (
            await db.execute(
                select(Employee, Role.code)
                .join(Device, Device.id == Employee.device_id)
                .join(RoleAssignment, RoleAssignment.employee_id == Employee.id)
                .join(Role, Role.id == RoleAssignment.role_id)
                .where(
                    Device.id == device_id,
                    RoleAssignment.revoked_at.is_(None),
                    Role.code.in_([RoleCode.ADMINISTRATOR, RoleCode.CHIEF]),
                )
            )
        ).one_or_none()
        if row is None:
            raise RolePermissionDeniedError(
                "Only administrator or chief can manage roles"
            )
        return row[0], row[1]

    @staticmethod
    def _response(assignment: RoleAssignment, role: RoleCode) -> RoleAssignmentResponse:
        return RoleAssignmentResponse(
            id=assignment.id,
            employee_id=assignment.employee_id,
            role=role,
            assigned_by_employee_id=assignment.assigned_by_employee_id,
            assigned_at=assignment.assigned_at,
            revoked_at=assignment.revoked_at,
        )

    @staticmethod
    async def assign(
        db: AsyncSession,
        employee_id: UUID,
        requester_device_id: UUID,
        role_code: RoleCode,
    ) -> RoleAssignmentResponse:
        requester, requester_role = await RoleService._requester(
            db, requester_device_id
        )
        target = await db.get(Employee, employee_id)
        if target is None:
            raise EmployeeNotFoundError("Employee not found")
        current = await RoleService._active_assignment(db, employee_id)
        current_role = await db.get(Role, current.role_id) if current else None

        changes_chief = role_code == RoleCode.CHIEF or (
            current_role is not None and current_role.code == RoleCode.CHIEF
        )
        if changes_chief and requester_role != RoleCode.CHIEF:
            raise RolePermissionDeniedError("Only chief can assign or change chief role")
        if current_role is not None and current_role.code == role_code:
            raise RoleConflictError("Employee already has this role")
        if (
            current_role is not None
            and current_role.code == RoleCode.CHIEF
            and role_code != RoleCode.CHIEF
            and await RoleService._chief_count(db) <= 1
        ):
            raise RoleConflictError("The last chief role cannot be changed")

        role = await db.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise RoleConflictError("Role is not configured")
        if current is not None:
            current.revoked_at = datetime.now(timezone.utc)
            await db.flush()
        assignment = RoleAssignment(
            employee_id=target.id,
            role_id=role.id,
            assigned_by_employee_id=requester.id,
        )
        db.add(assignment)
        await db.flush()
        await NotificationService.notify_chiefs(
            db,
            NotificationType.ROLE_CHANGED,
            "role_assignment",
            assignment.id,
            {"employee_id": str(target.id), "role": role.code.value},
        )
        await db.commit()
        await db.refresh(assignment)
        return RoleService._response(assignment, role.code)

    @staticmethod
    async def revoke(
        db: AsyncSession, employee_id: UUID, requester_device_id: UUID
    ) -> RoleAssignmentResponse:
        _requester, requester_role = await RoleService._requester(
            db, requester_device_id
        )
        if await db.get(Employee, employee_id) is None:
            raise EmployeeNotFoundError("Employee not found")
        assignment = await RoleService._active_assignment(db, employee_id)
        if assignment is None:
            raise RoleConflictError("Employee has no active role")
        role = await db.get(Role, assignment.role_id)
        if role.code == RoleCode.CHIEF:
            if requester_role != RoleCode.CHIEF:
                raise RolePermissionDeniedError("Only chief can revoke chief role")
            if await RoleService._chief_count(db) <= 1:
                raise RoleConflictError("The last chief role cannot be revoked")
        assignment.revoked_at = datetime.now(timezone.utc)
        await NotificationService.notify_chiefs(
            db,
            NotificationType.ROLE_REVOKED,
            "role_assignment",
            assignment.id,
            {"employee_id": str(employee_id), "role": role.code.value},
        )
        await db.commit()
        await db.refresh(assignment)
        return RoleService._response(assignment, role.code)

    @staticmethod
    async def history(
        db: AsyncSession, employee_id: UUID, requester_device_id: UUID
    ) -> RoleHistoryResponse:
        await RoleService._requester(db, requester_device_id)
        if await db.get(Employee, employee_id) is None:
            raise EmployeeNotFoundError("Employee not found")
        rows = (
            await db.execute(
                select(RoleAssignment, Role.code)
                .join(Role, Role.id == RoleAssignment.role_id)
                .where(RoleAssignment.employee_id == employee_id)
                .order_by(RoleAssignment.assigned_at.desc())
            )
        ).all()
        return RoleHistoryResponse(
            items=[RoleService._response(assignment, code) for assignment, code in rows]
        )
