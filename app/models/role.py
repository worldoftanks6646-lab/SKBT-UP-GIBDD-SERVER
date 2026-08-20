import enum
import uuid

from sqlalchemy import Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RoleCode(str, enum.Enum):
    INSPECTOR = "inspector"
    ADMINISTRATOR = "administrator"
    CHIEF = "chief"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[RoleCode] = mapped_column(
        SqlEnum(
            RoleCode,
            name="role_code",
            values_callable=lambda items: [item.value for item in items],
        ),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    assignments = relationship("RoleAssignment", back_populates="role")
