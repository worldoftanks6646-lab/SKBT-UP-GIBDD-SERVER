from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import (
    Device,
    Employee,
    Notification,
    NotificationType,
    Role,
    RoleAssignment,
    RoleCode,
)
from app.schemas.notification import NotificationListResponse, NotificationResponse


class NotificationEmployeeNotFoundError(ValueError):
    pass


class NotificationNotFoundError(ValueError):
    pass


class NotificationService:
    @staticmethod
    async def _employee_id(db: AsyncSession, device_id: UUID) -> UUID:
        employee_id = await db.scalar(
            select(Employee.id).join(Device, Device.id == Employee.device_id).where(Device.id == device_id)
        )
        if employee_id is None:
            raise NotificationEmployeeNotFoundError("Employee device not found")
        return employee_id

    @staticmethod
    async def notify_chiefs(
        db: AsyncSession,
        notification_type: NotificationType,
        related_entity_type: str,
        related_entity_id: UUID,
        payload: dict,
    ) -> None:
        chief_ids = list(
            (
                await db.scalars(
                    select(Employee.id)
                    .join(RoleAssignment, RoleAssignment.employee_id == Employee.id)
                    .join(Role, Role.id == RoleAssignment.role_id)
                    .where(RoleAssignment.revoked_at.is_(None), Role.code == RoleCode.CHIEF)
                )
            ).all()
        )
        db.add_all(
            [
                Notification(
                    recipient_employee_id=employee_id,
                    type=notification_type,
                    related_entity_type=related_entity_type,
                    related_entity_id=related_entity_id,
                    payload=payload,
                )
                for employee_id in chief_ids
            ]
        )

    @staticmethod
    async def list_for_employee(
        db: AsyncSession,
        requester_device_id: UUID,
        limit: int,
        before: datetime | None,
        unread_only: bool,
    ) -> NotificationListResponse:
        employee_id = await NotificationService._employee_id(db, requester_device_id)
        statement = (
            select(Notification)
            .where(Notification.recipient_employee_id == employee_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit + 1)
        )
        if before is not None:
            statement = statement.where(Notification.created_at < before)
        if unread_only:
            statement = statement.where(Notification.is_read.is_(False))
        notifications = list((await db.scalars(statement)).all())
        has_more = len(notifications) > limit
        notifications = notifications[:limit]
        return NotificationListResponse(
            items=notifications,
            next_before=notifications[-1].created_at if has_more and notifications else None,
        )

    @staticmethod
    async def mark_read(
        db: AsyncSession, notification_id: UUID, requester_device_id: UUID
    ) -> NotificationResponse:
        employee_id = await NotificationService._employee_id(db, requester_device_id)
        notification = await db.get(Notification, notification_id)
        if notification is None or notification.recipient_employee_id != employee_id:
            raise NotificationNotFoundError("Notification not found")
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = func.now()
            await db.commit()
            await db.refresh(notification)
        return NotificationResponse.model_validate(notification)
