from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, DeviceType, Employee, Role, RoleAssignment, RoleCode, Witness
from app.schemas.employee import (
    DeviceListResponse,
    DeviceResponse,
    EmployeeListResponse,
    EmployeeResponse,
)


class EmployeeProfileNotFoundError(ValueError):
    pass


class EmployeeProfilePermissionDeniedError(PermissionError):
    pass


class EmployeeService:
    @staticmethod
    async def _requester_role(
        db: AsyncSession, requester_device_id: UUID
    ) -> RoleCode:
        role = await db.scalar(
            select(Role.code)
            .join(RoleAssignment, RoleAssignment.role_id == Role.id)
            .join(Employee, Employee.id == RoleAssignment.employee_id)
            .where(
                Employee.device_id == requester_device_id,
                RoleAssignment.revoked_at.is_(None),
            )
        )
        if role not in (RoleCode.ADMINISTRATOR, RoleCode.CHIEF):
            raise EmployeeProfilePermissionDeniedError(
                "Only administrator or chief can view employee and device lists"
            )
        return role

    @staticmethod
    def _employee_response(row) -> EmployeeResponse:
        employee, role = row
        return EmployeeResponse(
            id=employee.id,
            device_id=employee.device_id,
            role=role,
            registered_at=employee.registered_at,
            last_activity_at=employee.last_activity_at,
        )

    @staticmethod
    async def me(db: AsyncSession, device_id: UUID) -> EmployeeResponse:
        row = (
            await db.execute(
                select(Employee, Role.code)
                .outerjoin(
                    RoleAssignment,
                    (RoleAssignment.employee_id == Employee.id)
                    & (RoleAssignment.revoked_at.is_(None)),
                )
                .outerjoin(Role, Role.id == RoleAssignment.role_id)
                .where(Employee.device_id == device_id)
            )
        ).one_or_none()
        if row is None:
            raise EmployeeProfileNotFoundError("Employee device not found")
        return EmployeeService._employee_response(row)

    @staticmethod
    async def list_employees(
        db: AsyncSession,
        requester_device_id: UUID,
        limit: int,
        before: datetime | None,
    ) -> EmployeeListResponse:
        requester_role = await EmployeeService._requester_role(
            db, requester_device_id
        )
        statement = (
            select(Employee, Role.code)
            .outerjoin(
                RoleAssignment,
                (RoleAssignment.employee_id == Employee.id)
                & (RoleAssignment.revoked_at.is_(None)),
            )
            .outerjoin(Role, Role.id == RoleAssignment.role_id)
            .order_by(Employee.registered_at.desc(), Employee.id.desc())
            .limit(limit + 1)
        )
        if requester_role == RoleCode.ADMINISTRATOR:
            statement = statement.where(
                Role.code.in_([RoleCode.INSPECTOR, RoleCode.ADMINISTRATOR])
            )
        if before is not None:
            statement = statement.where(Employee.registered_at < before)
        rows = list((await db.execute(statement)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [EmployeeService._employee_response(row) for row in rows]
        return EmployeeListResponse(
            items=items,
            next_before=items[-1].registered_at if has_more and items else None,
        )

    @staticmethod
    async def get_employee(
        db: AsyncSession, employee_id: UUID, requester_device_id: UUID
    ) -> EmployeeResponse:
        requester_role = await EmployeeService._requester_role(
            db, requester_device_id
        )
        row = (
            await db.execute(
                select(Employee, Role.code)
                .outerjoin(
                    RoleAssignment,
                    (RoleAssignment.employee_id == Employee.id)
                    & (RoleAssignment.revoked_at.is_(None)),
                )
                .outerjoin(Role, Role.id == RoleAssignment.role_id)
                .where(Employee.id == employee_id)
            )
        ).one_or_none()
        if row is None:
            raise EmployeeProfileNotFoundError("Employee not found")
        if requester_role == RoleCode.ADMINISTRATOR and row[1] not in (
            RoleCode.INSPECTOR,
            RoleCode.ADMINISTRATOR,
        ):
            raise EmployeeProfilePermissionDeniedError(
                "Administrator cannot view this employee"
            )
        return EmployeeService._employee_response(row)

    @staticmethod
    def _device_response(row) -> DeviceResponse:
        device, employee_id, witness_id, role, ban_level = row
        return DeviceResponse(
            id=device.id,
            type=device.type,
            platform=device.platform,
            app_version=device.app_version,
            registered_at=device.registered_at,
            last_activity_at=device.last_activity_at,
            employee_id=employee_id,
            witness_id=witness_id,
            role=role,
            ban_level=ban_level if device.type == DeviceType.WITNESS else None,
        )

    @staticmethod
    def _device_statement():
        return (
            select(
                Device,
                Employee.id,
                Witness.id,
                Role.code,
                Witness.ban_level,
            )
            .outerjoin(Employee, Employee.device_id == Device.id)
            .outerjoin(Witness, Witness.device_id == Device.id)
            .outerjoin(
                RoleAssignment,
                (RoleAssignment.employee_id == Employee.id)
                & (RoleAssignment.revoked_at.is_(None)),
            )
            .outerjoin(Role, Role.id == RoleAssignment.role_id)
        )

    @staticmethod
    async def list_devices(
        db: AsyncSession,
        requester_device_id: UUID,
        limit: int,
        before: datetime | None,
        device_type: DeviceType | None,
    ) -> DeviceListResponse:
        requester_role = await EmployeeService._requester_role(
            db, requester_device_id
        )
        statement = (
            EmployeeService._device_statement()
            .order_by(Device.registered_at.desc(), Device.id.desc())
            .limit(limit + 1)
        )
        if requester_role == RoleCode.ADMINISTRATOR:
            statement = statement.where(
                or_(
                    Device.type == DeviceType.WITNESS,
                    Role.code.in_([RoleCode.INSPECTOR, RoleCode.ADMINISTRATOR]),
                )
            )
        if device_type is not None:
            statement = statement.where(Device.type == device_type)
        if before is not None:
            statement = statement.where(Device.registered_at < before)
        rows = list((await db.execute(statement)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [EmployeeService._device_response(row) for row in rows]
        return DeviceListResponse(
            items=items,
            next_before=items[-1].registered_at if has_more and items else None,
        )

    @staticmethod
    async def get_device(
        db: AsyncSession, device_id: UUID, requester_device_id: UUID
    ) -> DeviceResponse:
        if device_id == requester_device_id:
            row = (
                await db.execute(
                    EmployeeService._device_statement().where(Device.id == device_id)
                )
            ).one_or_none()
            if row is None:
                raise EmployeeProfileNotFoundError("Device not found")
            return EmployeeService._device_response(row)

        requester_role = await EmployeeService._requester_role(
            db, requester_device_id
        )
        row = (
            await db.execute(
                EmployeeService._device_statement().where(Device.id == device_id)
            )
        ).one_or_none()
        if row is None:
            raise EmployeeProfileNotFoundError("Device not found")
        if (
            requester_role == RoleCode.ADMINISTRATOR
            and row[0].type == DeviceType.EMPLOYEE
            and row[3] not in (RoleCode.INSPECTOR, RoleCode.ADMINISTRATOR)
        ):
            raise EmployeeProfilePermissionDeniedError(
                "Administrator cannot view this device"
            )
        return EmployeeService._device_response(row)
