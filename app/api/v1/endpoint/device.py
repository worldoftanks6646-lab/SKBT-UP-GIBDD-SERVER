from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.device import DeviceRegisterRequest, DeviceRegisterResponse
from app.services.device_service import DeviceService, DeviceTypeConflictError


router = APIRouter(prefix="/devices", tags=["devices"])


@router.post(
    "/register",
    response_model=DeviceRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_device(
    request: DeviceRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeviceRegisterResponse:
    try:
        result = await DeviceService.register_device(db, request)
        if not result.is_new:
            response.status_code = status.HTTP_200_OK
        return result
    except DeviceTypeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
