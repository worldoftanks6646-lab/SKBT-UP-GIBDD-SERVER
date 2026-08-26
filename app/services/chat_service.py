from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chat, Device, DeviceType, Employee, Message, MessageSenderType, Role, RoleCode, WitnessBan
from app.models.role_assignment import RoleAssignment
from app.schemas.chat import ChatListItem, ChatListResponse


class EmployeeDeviceNotFoundError(ValueError):
    pass


class EmployeeRoleRequiredError(PermissionError):
    pass


class ChatService:
    @staticmethod
    async def _authorize_employee(db: AsyncSession, device_id: UUID) -> RoleCode:
        row = (
            await db.execute(
            select(Employee.id, Role.code)
            .join(Device, Device.id == Employee.device_id)
            .join(RoleAssignment, RoleAssignment.employee_id == Employee.id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .where(Device.id == device_id, Device.type == DeviceType.EMPLOYEE)
            .where(RoleAssignment.revoked_at.is_(None))
            )
        ).one_or_none()
        if row is None:
            employee_exists = await db.scalar(
                select(Employee.id).join(Device, Device.id == Employee.device_id).where(Device.id == device_id)
            )
            if employee_exists is None:
                raise EmployeeDeviceNotFoundError("Employee device not found")
            raise EmployeeRoleRequiredError("Employee has no assigned role")
        return row[1]

    @staticmethod
    async def list_for_employee(
        db: AsyncSession,
        requester_device_id: UUID,
        limit: int,
        before: datetime | None,
    ) -> ChatListResponse:
        requester_role = await ChatService._authorize_employee(db, requester_device_id)
        active_ban = exists(
            select(WitnessBan.id).where(
                WitnessBan.witness_id == Chat.witness_id,
                WitnessBan.is_active.is_(True),
                WitnessBan.revoked_at.is_(None),
                or_(WitnessBan.expires_at.is_(None), WitnessBan.expires_at > func.now()),
            )
        )

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
            select(Chat, last_text.label("last_message_text"), unread_count.label("unread_count"), active_ban.label("is_banned"))
            .order_by(activity_at.desc(), Chat.id.desc())
            .limit(limit + 1)
        )
        if requester_role != RoleCode.CHIEF:
            statement = statement.where(~active_ban)
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
                is_banned=is_banned,
            )
            for chat, text, count, is_banned in rows
        ]
        next_before = None
        if has_more and items:
            next_before = items[-1].last_message_at or items[-1].created_at
        return ChatListResponse(items=items, next_before=next_before)
