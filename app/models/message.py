import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MessageType(str, enum.Enum):
    TEXT = "text"
    MEDIA = "media"
    GEOLOCATION = "geolocation"


class MessageSenderType(str, enum.Enum):
    WITNESS = "witness"
    EMPLOYEE = "employee"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True
    )
    sender_type: Mapped[MessageSenderType] = mapped_column(
        SqlEnum(
            MessageSenderType,
            name="message_sender_type",
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
    )
    message_type: Mapped[MessageType] = mapped_column(
        SqlEnum(
            MessageType,
            name="message_type",
            values_callable=lambda items: [item.value for item in items],
        ),
        nullable=False,
    )
    text: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    chat = relationship("Chat", back_populates="messages")
    sender_device = relationship("Device", back_populates="messages")
    attachments = relationship(
        "Attachment", back_populates="message", cascade="all, delete-orphan"
    )
