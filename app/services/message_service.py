from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import (
    Chat,
    Attachment,
    Device,
    DeviceType,
    Employee,
    Message,
    MessageSenderType,
    MessageType,
    MessageTemplate,
    LocationSession,
    RoleAssignment,
    Witness,
)
from app.schemas.message import (
    MessageListResponse,
    MessageResponse,
    MessageTemplateListResponse,
)
from app.services.witness_access import witness_has_active_ban


class ChatNotFoundError(ValueError):
    pass


class MessageNotFoundError(ValueError):
    pass


class DeviceNotFoundError(ValueError):
    pass


class ChatAccessDeniedError(PermissionError):
    pass


class MessageTemplateNotFoundError(ValueError):
    pass


class MessageService:
    @staticmethod
    async def _get_chat(db: AsyncSession, chat_id: UUID) -> Chat:
        chat = await db.get(Chat, chat_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found")
        return chat

    @staticmethod
    async def _authorize_device(
        db: AsyncSession, chat: Chat, device_id: UUID
    ) -> Device:
        device = await db.get(Device, device_id)
        if device is None:
            raise DeviceNotFoundError("Device not found")

        if device.type == DeviceType.WITNESS:
            witness = await db.scalar(
                select(Witness).where(Witness.device_id == device.id)
            )
            if witness is None or witness.id != chat.witness_id:
                raise ChatAccessDeniedError("Device has no access to this chat")
            if await witness_has_active_ban(db, witness):
                raise ChatAccessDeniedError("Banned witness cannot access the chat")
        else:
            employee_id = await db.scalar(
                select(Employee.id).where(Employee.device_id == device.id)
            )
            has_role = (
                await db.scalar(
                    select(RoleAssignment.id).where(
                        RoleAssignment.employee_id == employee_id,
                        RoleAssignment.revoked_at.is_(None),
                    )
                )
                if employee_id is not None
                else None
            )
            if has_role is None:
                raise ChatAccessDeniedError("Employee has no assigned role")

        return device

    @staticmethod
    async def create_text_message(
        db: AsyncSession,
        chat_id: UUID,
        sender_device_id: UUID,
        text: str,
    ) -> MessageResponse:
        chat = await MessageService._get_chat(db, chat_id)
        sender = await MessageService._authorize_device(db, chat, sender_device_id)
        if sender.type == DeviceType.EMPLOYEE:
            raise ChatAccessDeniedError(
                "Employee must send a predefined message template"
            )
        sender_type = (
            MessageSenderType.WITNESS
            if sender.type == DeviceType.WITNESS
            else MessageSenderType.EMPLOYEE
        )
        message = Message(
            chat_id=chat.id,
            sender_device_id=sender.id,
            sender_type=sender_type,
            message_type=MessageType.TEXT,
            text=text,
        )
        db.add(message)
        chat.last_message_at = func.now()
        await db.commit()
        await db.refresh(message)
        return MessageResponse.model_validate(message)

    @staticmethod
    async def list_templates(
        db: AsyncSession, requester_device_id: UUID
    ) -> MessageTemplateListResponse:
        employee_id = await db.scalar(
            select(Employee.id).where(Employee.device_id == requester_device_id)
        )
        if employee_id is None:
            raise DeviceNotFoundError("Employee device not found")
        active_role = await db.scalar(
            select(RoleAssignment.id).where(
                RoleAssignment.employee_id == employee_id,
                RoleAssignment.revoked_at.is_(None),
            )
        )
        if active_role is None:
            raise ChatAccessDeniedError("Employee has no assigned role")
        templates = list(
            (
                await db.scalars(
                    select(MessageTemplate)
                    .where(MessageTemplate.is_active.is_(True))
                    .order_by(MessageTemplate.code)
                )
            ).all()
        )
        return MessageTemplateListResponse(items=templates)

    @staticmethod
    async def create_template_message(
        db: AsyncSession,
        chat_id: UUID,
        sender_device_id: UUID,
        template_id: UUID,
    ) -> MessageResponse:
        chat = await MessageService._get_chat(db, chat_id)
        sender = await MessageService._authorize_device(db, chat, sender_device_id)
        if sender.type != DeviceType.EMPLOYEE:
            raise ChatAccessDeniedError("Only employee can send a message template")
        template = await db.get(MessageTemplate, template_id)
        if template is None or not template.is_active:
            raise MessageTemplateNotFoundError("Message template not found")
        message = Message(
            chat_id=chat.id,
            sender_device_id=sender.id,
            sender_type=MessageSenderType.EMPLOYEE,
            message_type=MessageType.TEXT,
            text=template.text,
        )
        db.add(message)
        chat.last_message_at = func.now()
        await db.commit()
        await db.refresh(message)
        return MessageResponse.model_validate(message)

    @staticmethod
    async def list_messages(
        db: AsyncSession,
        chat_id: UUID,
        requester_device_id: UUID,
        limit: int,
        before: datetime | None,
    ) -> MessageListResponse:
        chat = await MessageService._get_chat(db, chat_id)
        await MessageService._authorize_device(db, chat, requester_device_id)
        statement = (
            select(Message)
            .where(Message.chat_id == chat.id, Message.deleted.is_(False))
            .order_by(Message.sent_at.desc(), Message.id.desc())
            .limit(limit + 1)
        )
        if before is not None:
            statement = statement.where(Message.sent_at < before)
        messages = list((await db.scalars(statement)).all())
        has_more = len(messages) > limit
        messages = messages[:limit]
        next_before = messages[-1].sent_at if has_more and messages else None
        messages.reverse()
        attachment_rows = (
            await db.execute(
                select(Attachment.message_id, Attachment.id).where(
                    Attachment.message_id.in_([message.id for message in messages]),
                    Attachment.deleted_at.is_(None),
                )
            )
        ).all() if messages else []
        attachment_ids = dict(attachment_rows)
        location_rows = (
            await db.execute(
                select(LocationSession.message_id, LocationSession.id).where(
                    LocationSession.message_id.in_([message.id for message in messages])
                )
            )
        ).all() if messages else []
        location_ids = dict(location_rows)
        items = [
            MessageResponse.model_validate(message).model_copy(
                update={
                    "attachment_id": attachment_ids.get(message.id),
                    "location_session_id": location_ids.get(message.id),
                }
            )
            for message in messages
        ]
        return MessageListResponse(items=items, next_before=next_before)

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        chat_id: UUID,
        message_id: UUID,
        requester_device_id: UUID,
    ) -> MessageResponse:
        chat = await MessageService._get_chat(db, chat_id)
        await MessageService._authorize_device(db, chat, requester_device_id)
        message = await db.get(Message, message_id)
        if message is None or message.chat_id != chat.id or message.deleted:
            raise MessageNotFoundError("Message not found")
        if message.sender_device_id == requester_device_id:
            raise ChatAccessDeniedError("Sender cannot mark own message as read")
        if message.read_at is None:
            message.read_at = func.now()
            await db.commit()
            await db.refresh(message)
        return MessageResponse.model_validate(message)
