from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.role import RoleCode


class RoleChangeRequest(BaseModel):
    requester_device_id: UUID
    role: RoleCode


class RoleAssignmentResponse(BaseModel):
    id: UUID
    employee_id: UUID
    role: RoleCode
    assigned_by_employee_id: UUID | None
    assigned_at: datetime
    revoked_at: datetime | None


class RoleHistoryResponse(BaseModel):
    items: list[RoleAssignmentResponse]
