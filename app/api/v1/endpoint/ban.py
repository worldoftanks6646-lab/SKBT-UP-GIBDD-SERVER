from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.schemas.ban import ActiveBanResponse, BanCreateRequest, BanListResponse, BanResponse, BanRevokeRequest
from app.services.ban_service import (
    BanConflictError,
    BanNotFoundError,
    BanPermissionDeniedError,
    BanService,
    WitnessNotFoundError,
)
from app.services.push_service import PushService
from app.services.websocket_manager import chat_connections


router = APIRouter(prefix="/witnesses", tags=["bans"])


def ban_error_to_http(error: Exception) -> HTTPException:
    if isinstance(error, BanPermissionDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, BanConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get(
    "/me/active-ban",
    response_model=ActiveBanResponse,
    response_model_exclude_none=True,
)
async def get_own_active_ban(
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> ActiveBanResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await BanService.own_active_ban(db, requester_device_id)
    except BanPermissionDeniedError as error:
        raise ban_error_to_http(error) from error


@router.post("/{witness_id}/bans", response_model=BanResponse, status_code=201)
async def issue_ban(
    witness_id: UUID,
    request: BanCreateRequest,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> BanResponse:
    verify_device_id(authenticated_device_id, request.issued_by_device_id)
    try:
        result = await BanService.issue(db, witness_id, request)
        await PushService.notify_chiefs(
            db, "ban.issued", "ГИБДД-Очевидец", "Очевидцу выдан бан", result.id
        )
        await PushService.notify_witness(
            db,
            witness_id,
            "observer_banned",
            "ГИБДД-Очевидец",
            "Доступ к приложению ограничен",
            {
                "ban_id": str(result.id),
                "ban_level": str(result.ban_level),
                "issued_at": result.issued_at.isoformat().replace("+00:00", "Z"),
                "expires_at": (
                    result.expires_at.isoformat().replace("+00:00", "Z")
                    if result.expires_at is not None
                    else ""
                ),
                "reason": result.reason,
            },
        )
        chat_id = await BanService.witness_chat_id(db, witness_id)
        if chat_id is not None:
            await chat_connections.broadcast(
                chat_id,
                {
                    "event": "observer_banned",
                    "data": {
                        "id": str(result.id),
                        "ban_level": result.ban_level,
                        "issued_at": result.issued_at.isoformat().replace("+00:00", "Z"),
                        "expires_at": (
                            result.expires_at.isoformat().replace("+00:00", "Z")
                            if result.expires_at is not None
                            else None
                        ),
                        "reason": result.reason,
                    },
                },
            )
        return result
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
        result = await BanService.revoke(db, witness_id, ban_id, request)
        await PushService.notify_chiefs(
            db, "ban.revoked", "ГИБДД-Очевидец", "Бан очевидца снят", result.id
        )
        await PushService.notify_witness(
            db,
            witness_id,
            "observer_ban_revoked",
            "ГИБДД-Очевидец",
            "Блокировка снята",
            {"ban_id": str(result.id)},
        )
        return result
    except (
        WitnessNotFoundError,
        BanNotFoundError,
        BanConflictError,
        BanPermissionDeniedError,
    ) as error:
        raise ban_error_to_http(error) from error
