import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SqlEnum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DeviceType(str, enum.Enum):
    WITNESS = "witness"
    EMPLOYEE = "employee"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fingerprint_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    type: Mapped[DeviceType] = mapped_column(
        SqlEnum(
            DeviceType,
            name="device_type",
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    witness = relationship(
        "Witness", back_populates="device", uselist=False, cascade="all, delete-orphan"
    )
    employee = relationship(
        "Employee", back_populates="device", uselist=False, cascade="all, delete-orphan"
    )
