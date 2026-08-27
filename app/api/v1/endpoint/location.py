from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.schemas.location import (
    LiveLocationStart,
    LocationFinishRequest,
    LocationMessageResponse,
    LocationPointCreate,
    LocationPointResponse,
    LocationSessionResponse,
)
from app.services.location_service import (
    LocationService,
    LocationSessionNotFoundError,
    LocationSessionStateError,
)
from app.services.message_service import ChatAccessDeniedError, ChatNotFoundError, DeviceNotFoundError
from app.services.websocket_manager import chat_connections
from app.services.push_service import PushService


router = APIRouter(tags=["geolocation"])


def location_error(error: Exception) -> HTTPException:
    if isinstance(error, ChatAccessDeniedError):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, LocationSessionStateError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=404, detail=str(error))


@router.post("/chats/{chat_id}/locations/static", response_model=LocationMessageResponse, status_code=201)
async def create_static_location(chat_id: UUID, payload: LocationPointCreate, db: AsyncSession = Depends(get_db), authenticated_device_id: UUID | None = Depends(get_current_device_id)) -> LocationMessageResponse:
    verify_device_id(authenticated_device_id, payload.sender_device_id)
    try:
        result = await LocationService.create_static(db, chat_id, payload)
        await PushService.notify_chat_message(
            db,
            chat_id,
            payload.sender_device_id,
            result.message.sender_type.value,
            result.message.id,
            result.message.message_type.value,
        )
        await chat_connections.broadcast(chat_id, {"event": "message.created", "data": result.message.model_dump(mode="json")})
        return result
    except (ChatAccessDeniedError, ChatNotFoundError, DeviceNotFoundError) as error:
        raise location_error(error) from error


@router.post("/chats/{chat_id}/locations/live", response_model=LocationMessageResponse, status_code=201)
async def start_live_location(chat_id: UUID, payload: LiveLocationStart, db: AsyncSession = Depends(get_db), authenticated_device_id: UUID | None = Depends(get_current_device_id)) -> LocationMessageResponse:
    verify_device_id(authenticated_device_id, payload.sender_device_id)
    try:
        result = await LocationService.start_live(db, chat_id, payload)
        await PushService.notify_chat_message(
            db,
            chat_id,
            payload.sender_device_id,
            result.message.sender_type.value,
            result.message.id,
            result.message.message_type.value,
        )
        await chat_connections.broadcast(chat_id, {"event": "message.created", "data": result.message.model_dump(mode="json")})
        return result
    except (ChatAccessDeniedError, ChatNotFoundError, DeviceNotFoundError) as error:
        raise location_error(error) from error


@router.post("/location-sessions/{session_id}/points", response_model=LocationPointResponse, status_code=201)
async def add_live_location_point(session_id: UUID, payload: LocationPointCreate, db: AsyncSession = Depends(get_db), authenticated_device_id: UUID | None = Depends(get_current_device_id)) -> LocationPointResponse:
    verify_device_id(authenticated_device_id, payload.sender_device_id)
    try:
        point, chat_id = await LocationService.add_point(db, session_id, payload)
        await chat_connections.broadcast(
            chat_id,
            {
                "event": "location.point",
                "session_id": str(session_id),
                "data": point.model_dump(mode="json"),
            },
        )
        return point
    except (ChatAccessDeniedError, ChatNotFoundError, DeviceNotFoundError, LocationSessionNotFoundError, LocationSessionStateError) as error:
        raise location_error(error) from error


@router.get("/location-sessions/{session_id}", response_model=LocationSessionResponse)
async def get_location_session(session_id: UUID, requester_device_id: UUID, db: AsyncSession = Depends(get_db), authenticated_device_id: UUID | None = Depends(get_current_device_id)) -> LocationSessionResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await LocationService.get(db, session_id, requester_device_id)
    except (ChatAccessDeniedError, ChatNotFoundError, DeviceNotFoundError, LocationSessionNotFoundError) as error:
        raise location_error(error) from error


@router.patch("/location-sessions/{session_id}/finish", response_model=LocationSessionResponse)
async def finish_live_location(session_id: UUID, payload: LocationFinishRequest, db: AsyncSession = Depends(get_db), authenticated_device_id: UUID | None = Depends(get_current_device_id)) -> LocationSessionResponse:
    verify_device_id(authenticated_device_id, payload.sender_device_id)
    try:
        return await LocationService.finish(db, session_id, payload.sender_device_id)
    except (ChatAccessDeniedError, ChatNotFoundError, DeviceNotFoundError, LocationSessionNotFoundError, LocationSessionStateError) as error:
        raise location_error(error) from error
