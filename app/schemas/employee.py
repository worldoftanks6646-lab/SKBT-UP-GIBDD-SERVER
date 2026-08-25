from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.device import DeviceType
from app.models.role import RoleCode


class EmployeeResponse(BaseModel):
    id: UUID
    device_id: UUID
    role: RoleCode | None
    registered_at: datetime
    last_activity_at: datetime


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    next_before: datetime | None = None


class DeviceResponse(BaseModel):
    id: UUID
    type: DeviceType
    platform: str
    app_version: str
    registered_at: datetime
    last_activity_at: datetime
    employee_id: UUID | None = None
    witness_id: UUID | None = None
    role: RoleCode | None = None
    ban_level: int | None = None


class DeviceListResponse(BaseModel):
    items: list[DeviceResponse]
    next_before: datetime | None = None
