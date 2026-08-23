from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DeviceType,
    LocationPoint,
    LocationSession,
    LocationSessionStatus,
    LocationSessionType,
    Message,
    MessageSenderType,
    MessageType,
)
from app.schemas.location import (
    LiveLocationStart,
    LocationMessageResponse,
    LocationPointCreate,
    LocationPointResponse,
    LocationSessionResponse,
)
from app.schemas.message import MessageResponse
from app.services.message_service import ChatAccessDeniedError, MessageService


class LocationSessionNotFoundError(ValueError):
    pass


class LocationSessionStateError(ValueError):
    pass


class LocationService:
    @staticmethod
    def _point_response(point: LocationPoint) -> LocationPointResponse:
        return LocationPointResponse(
            id=point.id,
            latitude=point.latitude,
            longitude=point.longitude,
            accuracy=point.accuracy,
            captured_at=point.captured_at,
            sequence_number=point.sequence_number,
        )

    @staticmethod
    def _session_response(session: LocationSession, points: list[LocationPoint]) -> LocationSessionResponse:
        return LocationSessionResponse(
            id=session.id,
            message_id=session.message_id,
            type=session.type,
            status=session.status,
            started_at=session.started_at,
            expires_at=session.expires_at,
            finished_at=session.finished_at,
            points=[LocationService._point_response(point) for point in points],
        )

    @staticmethod
    async def _create_message(db: AsyncSession, chat_id: UUID, sender_device_id: UUID) -> tuple[Message, object]:
        chat = await MessageService._get_chat(db, chat_id)
        sender = await MessageService._authorize_device(db, chat, sender_device_id)
        message = Message(
            chat_id=chat.id,
            sender_device_id=sender.id,
            sender_type=MessageSenderType.WITNESS if sender.type == DeviceType.WITNESS else MessageSenderType.EMPLOYEE,
            message_type=MessageType.GEOLOCATION,
        )
        db.add(message)
        chat.last_message_at = func.now()
        await db.flush()
        return message, chat

    @staticmethod
    async def create_static(db: AsyncSession, chat_id: UUID, payload: LocationPointCreate) -> LocationMessageResponse:
        message, _chat = await LocationService._create_message(db, chat_id, payload.sender_device_id)
        now = datetime.now(timezone.utc)
        session = LocationSession(
            message_id=message.id,
            type=LocationSessionType.STATIC,
            status=LocationSessionStatus.FINISHED,
            finished_at=now,
        )
        db.add(session)
        await db.flush()
        point = LocationPoint(
            session_id=session.id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy=payload.accuracy,
            captured_at=payload.captured_at.astimezone(timezone.utc),
            sequence_number=1,
        )
        db.add(point)
        await db.commit()
        await db.refresh(message)
        await db.refresh(session)
        await db.refresh(point)
        return LocationMessageResponse(
            message=MessageResponse.model_validate(message).model_copy(update={"location_session_id": session.id}),
            session=LocationService._session_response(session, [point]),
        )

    @staticmethod
    async def start_live(db: AsyncSession, chat_id: UUID, payload: LiveLocationStart) -> LocationMessageResponse:
        message, _chat = await LocationService._create_message(db, chat_id, payload.sender_device_id)
        session = LocationSession(
            message_id=message.id,
            type=LocationSessionType.LIVE,
            status=LocationSessionStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=payload.duration_seconds),
        )
        db.add(session)
        await db.commit()
        await db.refresh(message)
        await db.refresh(session)
        return LocationMessageResponse(
            message=MessageResponse.model_validate(message).model_copy(update={"location_session_id": session.id}),
            session=LocationService._session_response(session, []),
        )

    @staticmethod
    async def _get_authorized_session(db: AsyncSession, session_id: UUID, requester_device_id: UUID) -> tuple[LocationSession, Message]:
        session = await db.get(LocationSession, session_id)
        if session is None:
            raise LocationSessionNotFoundError("Location session not found")
        message = await db.get(Message, session.message_id)
        if message is None or message.deleted:
            raise LocationSessionNotFoundError("Location session not found")
        chat = await MessageService._get_chat(db, message.chat_id)
        await MessageService._authorize_device(db, chat, requester_device_id)
        return session, message

    @staticmethod
    async def add_point(
        db: AsyncSession, session_id: UUID, payload: LocationPointCreate
    ) -> tuple[LocationPointResponse, UUID]:
        session, message = await LocationService._get_authorized_session(db, session_id, payload.sender_device_id)
        if message.sender_device_id != payload.sender_device_id:
            raise ChatAccessDeniedError("Only the live location sender can add points")
        now = datetime.now(timezone.utc)
        if session.status != LocationSessionStatus.ACTIVE:
            raise LocationSessionStateError("Location session is not active")
        if session.expires_at is not None and session.expires_at <= now:
            session.status = LocationSessionStatus.EXPIRED
            session.finished_at = now
            await db.commit()
            raise LocationSessionStateError("Location session has expired")
        last_sequence = await db.scalar(
            select(func.max(LocationPoint.sequence_number)).where(LocationPoint.session_id == session.id)
        )
        point = LocationPoint(
            session_id=session.id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy=payload.accuracy,
            captured_at=payload.captured_at.astimezone(timezone.utc),
            sequence_number=(last_sequence or 0) + 1,
        )
        db.add(point)
        await db.commit()
        await db.refresh(point)
        return LocationService._point_response(point), message.chat_id

    @staticmethod
    async def get(db: AsyncSession, session_id: UUID, requester_device_id: UUID) -> LocationSessionResponse:
        session, _message = await LocationService._get_authorized_session(db, session_id, requester_device_id)
        points = list((await db.scalars(select(LocationPoint).where(LocationPoint.session_id == session.id).order_by(LocationPoint.sequence_number))).all())
        return LocationService._session_response(session, points)

    @staticmethod
    async def finish(db: AsyncSession, session_id: UUID, sender_device_id: UUID) -> LocationSessionResponse:
        session, message = await LocationService._get_authorized_session(db, session_id, sender_device_id)
        if message.sender_device_id != sender_device_id:
            raise ChatAccessDeniedError("Only the live location sender can finish the session")
        if session.status != LocationSessionStatus.ACTIVE:
            raise LocationSessionStateError("Location session is not active")
        session.status = LocationSessionStatus.FINISHED
        session.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        points = list((await db.scalars(select(LocationPoint).where(LocationPoint.session_id == session.id).order_by(LocationPoint.sequence_number))).all())
        return LocationService._session_response(session, points)
