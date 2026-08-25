from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.models.device import DeviceType
from app.schemas.employee import (
    DeviceListResponse,
    DeviceResponse,
    EmployeeListResponse,
    EmployeeResponse,
)
from app.services.employee_service import (
    EmployeeProfileNotFoundError,
    EmployeeProfilePermissionDeniedError,
    EmployeeService,
)


employee_router = APIRouter(prefix="/employees", tags=["employees"])
device_router = APIRouter(prefix="/devices", tags=["devices"])
compatibility_router = APIRouter(prefix="/employee", tags=["employee compatibility"])


def employee_error(error: Exception) -> HTTPException:
    if isinstance(error, EmployeeProfilePermissionDeniedError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@employee_router.get("/me", response_model=EmployeeResponse)
async def current_employee(
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> EmployeeResponse:
    if authenticated_device_id is None:
        raise HTTPException(status_code=401, detail="Bearer access token is required")
    try:
        return await EmployeeService.me(db, authenticated_device_id)
    except EmployeeProfileNotFoundError as error:
        raise employee_error(error) from error


@employee_router.get("", response_model=EmployeeListResponse)
async def list_employees(
    requester_device_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> EmployeeListResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await EmployeeService.list_employees(
            db, requester_device_id, limit, before
        )
    except EmployeeProfilePermissionDeniedError as error:
        raise employee_error(error) from error


@employee_router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> EmployeeResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await EmployeeService.get_employee(
            db, employee_id, requester_device_id
        )
    except (
        EmployeeProfileNotFoundError,
        EmployeeProfilePermissionDeniedError,
    ) as error:
        raise employee_error(error) from error


@device_router.get("", response_model=DeviceListResponse)
async def list_devices(
    requester_device_id: UUID,
    device_type: DeviceType | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> DeviceListResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await EmployeeService.list_devices(
            db, requester_device_id, limit, before, device_type
        )
    except EmployeeProfilePermissionDeniedError as error:
        raise employee_error(error) from error


@device_router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> DeviceResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await EmployeeService.get_device(db, device_id, requester_device_id)
    except (
        EmployeeProfileNotFoundError,
        EmployeeProfilePermissionDeniedError,
    ) as error:
        raise employee_error(error) from error


@compatibility_router.get("/me", response_model=EmployeeResponse)
async def current_employee_compatibility(
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> EmployeeResponse:
    return await current_employee(db, authenticated_device_id)


@compatibility_router.get("/devices", response_model=DeviceListResponse)
async def list_employee_devices_compatibility(
    requester_device_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> DeviceListResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        return await EmployeeService.list_devices(
            db, requester_device_id, limit, before, DeviceType.EMPLOYEE
        )
    except EmployeeProfilePermissionDeniedError as error:
        raise employee_error(error) from error


@compatibility_router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_employee_device_compatibility(
    device_id: UUID,
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> DeviceResponse:
    return await get_device(
        device_id, requester_device_id, db, authenticated_device_id
    )
