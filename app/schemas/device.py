from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models.device import DeviceType
from app.models.role import RoleCode


FingerprintHash = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]


class DeviceRegisterRequest(BaseModel):
    fingerprint_hash: FingerprintHash
    type: DeviceType
    platform: str = Field(min_length=1, max_length=32)
    app_version: str = Field(min_length=1, max_length=32)

    @field_validator("fingerprint_hash")
    @classmethod
    def normalize_fingerprint(cls, value: str) -> str:
        return value.lower()


class DeviceRegisterResponse(BaseModel):
    device_id: UUID
    type: DeviceType
    is_new: bool
    witness_id: UUID | None = None
    employee_id: UUID | None = None
    role: RoleCode | None = None
    chat_id: UUID | None = None
    ban_level: int | None = None
    access_token: str
    token_type: str = "bearer"
