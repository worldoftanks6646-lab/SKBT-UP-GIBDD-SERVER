from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chat, Device, DeviceType, Employee, Message, MessageSenderType
from app.models.role_assignment import RoleAssignment
from app.schemas.chat import ChatListItem, ChatListResponse


class EmployeeDeviceNotFoundError(ValueError):
    pass


class EmployeeRoleRequiredError(PermissionError):
    pass


class ChatService:
    @staticmethod
    async def _authorize_employee(db: AsyncSession, device_id: UUID) -> None:
        employee_id = await db.scalar(
            select(Employee.id)
            .join(Device, Device.id == Employee.device_id)
            .where(Device.id == device_id, Device.type == DeviceType.EMPLOYEE)
        )
        if employee_id is None:
            raise EmployeeDeviceNotFoundError("Employee device not found")

        active_role = await db.scalar(
            select(RoleAssignment.id).where(
                RoleAssignment.employee_id == employee_id,
                RoleAssignment.revoked_at.is_(None),
            )
        )
        if active_role is None:
            raise EmployeeRoleRequiredError("Employee has no assigned role")

    @staticmethod
    async def list_for_employee(
        db: AsyncSession,
        requester_device_id: UUID,
        limit: int,
        before: datetime | None,
    ) -> ChatListResponse:
        await ChatService._authorize_employee(db, requester_device_id)

        last_text = (
            select(Message.text)
            .where(Message.chat_id == Chat.id, Message.deleted.is_(False))
            .order_by(Message.sent_at.desc(), Message.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        unread_count = (
            select(func.count(Message.id))
            .where(
                Message.chat_id == Chat.id,
                Message.sender_type == MessageSenderType.WITNESS,
                Message.read_at.is_(None),
                Message.deleted.is_(False),
            )
            .correlate(Chat)
            .scalar_subquery()
        )
        activity_at = func.coalesce(Chat.last_message_at, Chat.created_at)
        statement = (
            select(Chat, last_text.label("last_message_text"), unread_count.label("unread_count"))
            .order_by(activity_at.desc(), Chat.id.desc())
            .limit(limit + 1)
        )
        if before is not None:
            statement = statement.where(activity_at < before)

        rows = list((await db.execute(statement)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [
            ChatListItem(
                id=chat.id,
                witness_id=chat.witness_id,
                created_at=chat.created_at,
                last_message_at=chat.last_message_at,
                last_message_text=text,
                unread_count=count,
            )
            for chat, text, count in rows
        ]
        next_before = None
        if has_more and items:
            next_before = items[-1].last_message_at or items[-1].created_at
        return ChatListResponse(items=items, next_before=next_before)
