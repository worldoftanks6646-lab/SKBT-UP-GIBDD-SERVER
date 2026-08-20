from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import (
    Chat,
    Device,
    DeviceType,
    Employee,
    Role,
    RoleAssignment,
    RoleCode,
    Witness,
)
from app.schemas.device import DeviceRegisterRequest, DeviceRegisterResponse


class DeviceTypeConflictError(ValueError):
    pass


class DeviceService:
    @staticmethod
    async def _build_response(
        db: AsyncSession, device: Device, is_new: bool
    ) -> DeviceRegisterResponse:
        response = DeviceRegisterResponse(
            device_id=device.id,
            type=device.type,
            is_new=is_new,
        )

        if device.type == DeviceType.WITNESS:
            witness = await db.scalar(
                select(Witness).where(Witness.device_id == device.id)
            )
            chat = await db.scalar(select(Chat).where(Chat.witness_id == witness.id))
            response.witness_id = witness.id
            response.chat_id = chat.id
            response.ban_level = witness.ban_level
        else:
            employee = await db.scalar(
                select(Employee).where(Employee.device_id == device.id)
            )
            response.employee_id = employee.id
            response.role = await db.scalar(
                select(Role.code)
                .join(RoleAssignment, RoleAssignment.role_id == Role.id)
                .where(RoleAssignment.employee_id == employee.id)
            )

        return response

    @staticmethod
    async def _assign_chief_to_first_employee(
        db: AsyncSession, employee: Employee
    ) -> None:
        # Serializes only the short "first employee" decision across API workers.
        await db.execute(text("SELECT pg_advisory_xact_lock(741852963)"))
        another_employee_exists = await db.scalar(
            select(Employee.id).where(Employee.id != employee.id).limit(1)
        )
        if another_employee_exists is not None:
            return

        chief_role = await db.scalar(select(Role).where(Role.code == RoleCode.CHIEF))
        if chief_role is None:
            chief_role = Role(
                code=RoleCode.CHIEF,
                name="Начальник",
                description="Первый сотрудник с полными правами",
            )
            db.add(chief_role)
            await db.flush()

        db.add(RoleAssignment(employee_id=employee.id, role_id=chief_role.id))

    @staticmethod
    async def register_device(
        db: AsyncSession, payload: DeviceRegisterRequest
    ) -> DeviceRegisterResponse:
        statement = select(Device).where(
            Device.fingerprint_hash == payload.fingerprint_hash
        )
        device = await db.scalar(statement)

        if device is not None:
            if device.type != payload.type:
                raise DeviceTypeConflictError(
                    "An existing device cannot change its type"
                )
            device.platform = payload.platform
            device.app_version = payload.app_version
            device.last_activity_at = func.now()
            await db.commit()
            return await DeviceService._build_response(db, device, is_new=False)

        device = Device(
            fingerprint_hash=payload.fingerprint_hash,
            type=payload.type,
            platform=payload.platform,
            app_version=payload.app_version,
        )
        db.add(device)

        try:
            await db.flush()
            if device.type == DeviceType.WITNESS:
                witness = Witness(device_id=device.id)
                db.add(witness)
                await db.flush()
                db.add(Chat(witness_id=witness.id))
            else:
                employee = Employee(device_id=device.id)
                db.add(employee)
                await db.flush()
                await DeviceService._assign_chief_to_first_employee(db, employee)
            await db.commit()
        except IntegrityError:
            await db.rollback()
            device = await db.scalar(statement)
            if device is None:
                raise
            if device.type != payload.type:
                raise DeviceTypeConflictError(
                    "An existing device cannot change its type"
                )
            return await DeviceService._build_response(db, device, is_new=False)

        return await DeviceService._build_response(db, device, is_new=True)
