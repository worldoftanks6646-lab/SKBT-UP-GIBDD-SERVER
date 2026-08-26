from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.schemas.notification import NotificationListResponse, NotificationReadRequest, NotificationResponse
from app.services.notification_service import (
    NotificationEmployeeNotFoundError,
    NotificationNotFoundError,
    NotificationPermissionDeniedError,
    NotificationService,
)


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    requester_device_id: UUID,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> NotificationListResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await NotificationService.list_for_employee(
            db, requester_device_id, limit, before, unread_only
        )
    except NotificationPermissionDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except NotificationEmployeeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    payload: NotificationReadRequest,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> NotificationResponse:
    verify_device_id(authenticated_device_id, payload.requester_device_id)
    try:
        return await NotificationService.mark_read(
            db, notification_id, payload.requester_device_id
        )
    except NotificationPermissionDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (NotificationEmployeeNotFoundError, NotificationNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
