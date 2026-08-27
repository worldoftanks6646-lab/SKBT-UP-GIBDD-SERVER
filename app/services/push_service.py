import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Chat,
    Device,
    DeviceType,
    Employee,
    MessageSenderType,
    PushToken,
    Role,
    RoleAssignment,
    RoleCode,
    Witness,
)
from app.schemas.push import PushTokenResponse


logger = logging.getLogger(__name__)


class PushDeviceNotFoundError(ValueError):
    pass


class FcmClient:
    _credentials = None
    _scope = "https://www.googleapis.com/auth/firebase.messaging"

    @classmethod
    def configured(cls) -> bool:
        return bool(
            settings.PUSH_ENABLED
            and settings.FCM_PROJECT_ID
            and settings.FCM_SERVICE_ACCOUNT_FILE
            and Path(settings.FCM_SERVICE_ACCOUNT_FILE).is_file()
        )

    @classmethod
    def _access_token(cls) -> str:
        if cls._credentials is None:
            cls._credentials = service_account.Credentials.from_service_account_file(
                settings.FCM_SERVICE_ACCOUNT_FILE,
                scopes=[cls._scope],
            )
        if not cls._credentials.valid:
            cls._credentials.refresh(GoogleAuthRequest())
        return cls._credentials.token

    @classmethod
    def _send_sync(
        cls, tokens: list[str], title: str, body: str, data: dict[str, str]
    ) -> None:
        if not cls.configured() or not tokens:
            return
        access_token = cls._access_token()
        url = (
            "https://fcm.googleapis.com/v1/projects/"
            f"{settings.FCM_PROJECT_ID}/messages:send"
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=10) as client:
            for token in set(tokens):
                try:
                    response = client.post(
                        url,
                        headers=headers,
                        json={
                            "message": {
                                "token": token,
                                "notification": {"title": title, "body": body},
                                "data": data,
                                "android": {"priority": "high"},
                            }
                        },
                    )
                    response.raise_for_status()
                except Exception:
                    logger.exception("FCM push delivery failed")

    @classmethod
    async def send(
        cls, tokens: list[str], title: str, body: str, data: dict[str, str]
    ) -> None:
        if not cls.configured() or not tokens:
            return
        try:
            await asyncio.to_thread(cls._send_sync, tokens, title, body, data)
        except Exception:
            logger.exception("FCM push delivery initialization failed")


class PushService:
    @staticmethod
    async def notify_device(
        db: AsyncSession,
        device_id: UUID,
        event: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> None:
        if not FcmClient.configured():
            return
        token = await db.scalar(
            select(PushToken.token).where(PushToken.device_id == device_id)
        )
        if token is None:
            return
        payload = {"event": event}
        if data:
            payload.update(data)
        await FcmClient.send([token], title, body, payload)

    @staticmethod
    async def notify_witness(
        db: AsyncSession,
        witness_id: UUID,
        event: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> None:
        if not FcmClient.configured():
            return
        device_id = await db.scalar(
            select(Witness.device_id).where(Witness.id == witness_id)
        )
        if device_id is not None:
            await PushService.notify_device(db, device_id, event, title, body, data)

    @staticmethod
    async def notify_employee(
        db: AsyncSession,
        employee_id: UUID,
        event: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> None:
        if not FcmClient.configured():
            return
        device_id = await db.scalar(
            select(Employee.device_id).where(Employee.id == employee_id)
        )
        if device_id is not None:
            await PushService.notify_device(db, device_id, event, title, body, data)

    @staticmethod
    async def register(
        db: AsyncSession, device_id: UUID, token: str
    ) -> PushTokenResponse:
        if await db.get(Device, device_id) is None:
            raise PushDeviceNotFoundError("Device not found")
        normalized = token.strip()
        existing = await db.scalar(
            select(PushToken).where(PushToken.device_id == device_id)
        )
        token_owner = await db.scalar(
            select(PushToken).where(PushToken.token == normalized)
        )
        if token_owner is not None and token_owner.device_id != device_id:
            await db.delete(token_owner)
            await db.flush()
        now = datetime.now(timezone.utc)
        if existing is None:
            existing = PushToken(
                device_id=device_id,
                token=normalized,
                updated_at=now,
            )
            db.add(existing)
        else:
            existing.token = normalized
            existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        return PushTokenResponse(
            device_id=device_id,
            registered=True,
            updated_at=existing.updated_at,
        )

    @staticmethod
    async def unregister(db: AsyncSession, device_id: UUID) -> None:
        if await db.get(Device, device_id) is None:
            raise PushDeviceNotFoundError("Device not found")
        await db.execute(delete(PushToken).where(PushToken.device_id == device_id))
        await db.commit()

    @staticmethod
    async def _chat_recipient_tokens(
        db: AsyncSession, chat_id: UUID, sender_device_id: UUID
    ) -> list[str]:
        sender_type = await db.scalar(
            select(Device.type).where(Device.id == sender_device_id)
        )
        if sender_type == DeviceType.WITNESS:
            return list(
                (
                    await db.scalars(
                        select(PushToken.token)
                        .join(Device, Device.id == PushToken.device_id)
                        .join(Employee, Employee.device_id == Device.id)
                        .join(
                            RoleAssignment,
                            RoleAssignment.employee_id == Employee.id,
                        )
                        .where(RoleAssignment.revoked_at.is_(None))
                        .distinct()
                    )
                ).all()
            )
        return list(
            (
                await db.scalars(
                    select(PushToken.token)
                    .join(Device, Device.id == PushToken.device_id)
                    .join(Witness, Witness.device_id == Device.id)
                    .join(Chat, Chat.witness_id == Witness.id)
                    .where(Chat.id == chat_id)
                )
            ).all()
        )

    @staticmethod
    async def notify_chat_message(
        db: AsyncSession,
        chat_id: UUID,
        sender_device_id: UUID,
        sender_type: str,
        message_id: UUID,
        message_type: str,
    ) -> None:
        if not FcmClient.configured():
            return
        if sender_type == MessageSenderType.EMPLOYEE.value:
            token = await db.scalar(
                select(PushToken.token)
                .join(Device, Device.id == PushToken.device_id)
                .join(Witness, Witness.device_id == Device.id)
                .join(Chat, Chat.witness_id == Witness.id)
                .where(Chat.id == chat_id)
            )
            tokens = [token] if token is not None else []
        else:
            tokens = await PushService._chat_recipient_tokens(
                db, chat_id, sender_device_id
            )
        await FcmClient.send(
            tokens,
            "ГИБДД-Очевидец",
            "Новое сообщение",
            {
                "event": "message.created",
                "chat_id": str(chat_id),
                "message_id": str(message_id),
                "message_type": message_type,
            },
        )

    @staticmethod
    async def notify_chiefs(
        db: AsyncSession,
        event: str,
        title: str,
        body: str,
        related_entity_id: UUID,
    ) -> None:
        if not FcmClient.configured():
            return
        tokens = list(
            (
                await db.scalars(
                    select(PushToken.token)
                    .join(Device, Device.id == PushToken.device_id)
                    .join(Employee, Employee.device_id == Device.id)
                    .join(RoleAssignment, RoleAssignment.employee_id == Employee.id)
                    .join(Role, Role.id == RoleAssignment.role_id)
                    .where(
                        RoleAssignment.revoked_at.is_(None),
                        Role.code == RoleCode.CHIEF,
                    )
                )
            ).all()
        )
        await FcmClient.send(
            tokens,
            title,
            body,
            {"event": event, "related_entity_id": str(related_entity_id)},
        )
