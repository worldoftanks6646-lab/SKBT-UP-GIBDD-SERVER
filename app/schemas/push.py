from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PushTokenUpdate(BaseModel):
    token: str = Field(min_length=20, max_length=4096)

    @field_validator("token")
    @classmethod
    def normalize_token(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 20:
            raise ValueError("FCM token is too short")
        return value


class PushTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: UUID
    registered: bool
    updated_at: datetime
