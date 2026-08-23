import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class LocationSessionType(str, enum.Enum):
    STATIC = "static"
    LIVE = "live"


class LocationSessionStatus(str, enum.Enum):
    ACTIVE = "active"
    FINISHED = "finished"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class LocationSession(Base):
    __tablename__ = "location_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    type: Mapped[LocationSessionType] = mapped_column(
        SqlEnum(LocationSessionType, name="location_session_type", values_callable=lambda items: [item.value for item in items]),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[LocationSessionStatus] = mapped_column(
        SqlEnum(LocationSessionStatus, name="location_session_status", values_callable=lambda items: [item.value for item in items]),
        nullable=False,
    )

    message = relationship("Message", back_populates="location_session")
    points = relationship("LocationPoint", back_populates="session", cascade="all, delete-orphan")


class LocationPoint(Base):
    __tablename__ = "location_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("location_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    session = relationship("LocationSession", back_populates="points")
