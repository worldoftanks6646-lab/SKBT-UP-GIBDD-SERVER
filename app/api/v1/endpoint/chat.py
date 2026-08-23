from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.chat import ChatListResponse
from app.services.chat_service import (
    ChatService,
    EmployeeDeviceNotFoundError,
    EmployeeRoleRequiredError,
)


router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("", response_model=ChatListResponse)
async def list_employee_chats(
    requester_device_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> ChatListResponse:
    try:
        return await ChatService.list_for_employee(
            db, requester_device_id, limit, before
        )
    except EmployeeDeviceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except EmployeeRoleRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error
