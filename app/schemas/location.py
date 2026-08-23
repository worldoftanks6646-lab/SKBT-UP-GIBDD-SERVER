from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.location import LocationSessionStatus, LocationSessionType
from app.schemas.message import MessageResponse


class LocationPointCreate(BaseModel):
    sender_device_id: UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("captured_at")
    @classmethod
    def captured_at_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("captured_at must include timezone")
        return value


class LiveLocationStart(BaseModel):
    sender_device_id: UUID
    duration_seconds: int = Field(default=900, ge=60, le=3600)


class LocationFinishRequest(BaseModel):
    sender_device_id: UUID


class LocationPointResponse(BaseModel):
    id: UUID
    latitude: float
    longitude: float
    accuracy: float | None
    captured_at: datetime
    sequence_number: int


class LocationSessionResponse(BaseModel):
    id: UUID
    message_id: UUID
    type: LocationSessionType
    status: LocationSessionStatus
    started_at: datetime
    expires_at: datetime | None
    finished_at: datetime | None
    points: list[LocationPointResponse]


class LocationMessageResponse(BaseModel):
    message: MessageResponse
    session: LocationSessionResponse
