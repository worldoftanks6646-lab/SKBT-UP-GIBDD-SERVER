from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.schemas.ban import BanCreateRequest, BanListResponse, BanResponse, BanRevokeRequest
from app.services.ban_service import (
    BanConflictError,
    BanNotFoundError,
    BanPermissionDeniedError,
    BanService,
    WitnessNotFoundError,
)


router = APIRouter(prefix="/witnesses", tags=["bans"])


def ban_error_to_http(error: Exception) -> HTTPException:
    if isinstance(error, BanPermissionDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, BanConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("/{witness_id}/bans", response_model=BanResponse, status_code=201)
async def issue_ban(
    witness_id: UUID,
    request: BanCreateRequest,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> BanResponse:
    verify_device_id(authenticated_device_id, request.issued_by_device_id)
    try:
        return await BanService.issue(db, witness_id, request)
    except (WitnessNotFoundError, BanConflictError, BanPermissionDeniedError) as error:
        raise ban_error_to_http(error) from error


@router.get("/{witness_id}/bans", response_model=BanListResponse)
async def list_bans(
    witness_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> BanListResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await BanService.history(db, witness_id, requester_device_id)
    except (WitnessNotFoundError, BanPermissionDeniedError) as error:
        raise ban_error_to_http(error) from error


@router.patch("/{witness_id}/bans/{ban_id}/revoke", response_model=BanResponse)
async def revoke_ban(
    witness_id: UUID,
    ban_id: UUID,
    request: BanRevokeRequest,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> BanResponse:
    verify_device_id(authenticated_device_id, request.revoked_by_device_id)
    try:
        return await BanService.revoke(db, witness_id, ban_id, request)
    except (
        WitnessNotFoundError,
        BanNotFoundError,
        BanConflictError,
        BanPermissionDeniedError,
    ) as error:
        raise ban_error_to_http(error) from error
