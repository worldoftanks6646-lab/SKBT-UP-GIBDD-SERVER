"""Add static and live geolocation.

Revision ID: 0005_geolocation
Revises: 0004_attachments
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_geolocation"
down_revision: str | None = "0004_attachments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


session_type = postgresql.ENUM("static", "live", name="location_session_type", create_type=False)
session_status = postgresql.ENUM("active", "finished", "expired", "cancelled", name="location_session_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    session_type.create(bind, checkfirst=True)
    session_status.create(bind, checkfirst=True)
    op.create_table(
        "location_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", session_type, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", session_status, nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_table(
        "location_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["location_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_location_point_sequence"),
    )
    op.create_index("ix_location_points_session_id", "location_points", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_location_points_session_id", table_name="location_points")
    op.drop_table("location_points")
    op.drop_table("location_sessions")
    bind = op.get_bind()
    session_status.drop(bind, checkfirst=True)
    session_type.drop(bind, checkfirst=True)
