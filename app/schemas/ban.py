from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BanCreateRequest(BaseModel):
    issued_by_device_id: UUID
    ban_level: int = Field(ge=1, le=3)
    reason: str = Field(min_length=1, max_length=1000)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def expiration_must_include_timezone(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at must include timezone")
        return value


class BanRevokeRequest(BaseModel):
    revoked_by_device_id: UUID
    comment: str | None = Field(default=None, max_length=1000)


class BanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    witness_id: UUID
    ban_level: int
    reason: str
    issued_by_employee_id: UUID
    issued_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    revoked_by_employee_id: UUID | None
    comment: str | None


class BanListResponse(BaseModel):
    items: list[BanResponse]
