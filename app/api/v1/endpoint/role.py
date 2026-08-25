from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.schemas.role import RoleAssignmentResponse, RoleChangeRequest, RoleHistoryResponse
from app.services.role_service import (
    EmployeeNotFoundError,
    RoleConflictError,
    RolePermissionDeniedError,
    RoleService,
)
from app.services.push_service import PushService


router = APIRouter(prefix="/employees", tags=["roles"])
device_role_router = APIRouter(prefix="/devices", tags=["roles"])


def role_error_to_http(error: Exception) -> HTTPException:
    if isinstance(error, RolePermissionDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, RoleConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.put("/{employee_id}/role", response_model=RoleAssignmentResponse)
async def assign_role(
    employee_id: UUID,
    request: RoleChangeRequest,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> RoleAssignmentResponse:
    verify_device_id(authenticated_device_id, request.requester_device_id)
    try:
        result = await RoleService.assign(
            db, employee_id, request.requester_device_id, request.role
        )
        await PushService.notify_chiefs(
            db, "role.changed", "ГИБДД-Очевидец", "Изменена роль сотрудника", result.id
        )
        return result
    except (
        EmployeeNotFoundError,
        RolePermissionDeniedError,
        RoleConflictError,
    ) as error:
        raise role_error_to_http(error) from error


@device_role_router.put(
    "/{target_device_id}/role",
    response_model=RoleAssignmentResponse,
    summary="Assign a role using a device_id scanned from a QR code",
)
async def assign_role_by_qr(
    target_device_id: UUID,
    request: RoleChangeRequest,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> RoleAssignmentResponse:
    verify_device_id(authenticated_device_id, request.requester_device_id)
    try:
        result = await RoleService.assign_by_device(
            db, target_device_id, request.requester_device_id, request.role
        )
        await PushService.notify_chiefs(
            db, "role.changed", "ГИБДД-Очевидец", "Изменена роль сотрудника", result.id
        )
        return result
    except (
        EmployeeNotFoundError,
        RolePermissionDeniedError,
        RoleConflictError,
    ) as error:
        raise role_error_to_http(error) from error


@router.delete("/{employee_id}/role", response_model=RoleAssignmentResponse)
async def revoke_role(
    employee_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> RoleAssignmentResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        result = await RoleService.revoke(db, employee_id, requester_device_id)
        await PushService.notify_chiefs(
            db, "role.revoked", "ГИБДД-Очевидец", "Удалена роль сотрудника", result.id
        )
        return result
    except (
        EmployeeNotFoundError,
        RolePermissionDeniedError,
        RoleConflictError,
    ) as error:
        raise role_error_to_http(error) from error


@router.get("/{employee_id}/roles/history", response_model=RoleHistoryResponse)
async def role_history(
    employee_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> RoleHistoryResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await RoleService.history(db, employee_id, requester_device_id)
    except (EmployeeNotFoundError, RolePermissionDeniedError) as error:
        raise role_error_to_http(error) from error
