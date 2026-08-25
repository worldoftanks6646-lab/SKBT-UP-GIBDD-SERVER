from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.schemas.push import PushTokenResponse, PushTokenUpdate
from app.services.push_service import PushDeviceNotFoundError, PushService


router = APIRouter(prefix="/devices", tags=["push notifications"])


@router.put("/{device_id}/push-token", response_model=PushTokenResponse)
async def register_push_token(
    device_id: UUID,
    payload: PushTokenUpdate,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> PushTokenResponse:
    verify_device_id(authenticated_device_id, device_id)
    try:
        return await PushService.register(db, device_id, payload.token)
    except PushDeviceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{device_id}/push-token", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_push_token(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> Response:
    verify_device_id(authenticated_device_id, device_id)
    try:
        await PushService.unregister(db, device_id)
    except PushDeviceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
