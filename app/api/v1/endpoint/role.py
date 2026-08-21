from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.role import RoleAssignmentResponse, RoleChangeRequest, RoleHistoryResponse
from app.services.role_service import (
    EmployeeNotFoundError,
    RoleConflictError,
    RolePermissionDeniedError,
    RoleService,
)


router = APIRouter(prefix="/employees", tags=["roles"])


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
) -> RoleAssignmentResponse:
    try:
        return await RoleService.assign(
            db, employee_id, request.requester_device_id, request.role
        )
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
) -> RoleAssignmentResponse:
    try:
        return await RoleService.revoke(db, employee_id, requester_device_id)
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
) -> RoleHistoryResponse:
    try:
        return await RoleService.history(db, employee_id, requester_device_id)
    except (EmployeeNotFoundError, RolePermissionDeniedError) as error:
        raise role_error_to_http(error) from error
