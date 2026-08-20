import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class WitnessBan(Base):
    __tablename__ = "witness_bans"
    __table_args__ = (
        CheckConstraint("ban_level BETWEEN 1 AND 3", name="ck_witness_ban_level_history"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    witness_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("witnesses.id", ondelete="CASCADE"), nullable=False
    )
    ban_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    issued_by_employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id")
    )
    comment: Mapped[str | None] = mapped_column(Text)

    witness = relationship("Witness", back_populates="bans")
