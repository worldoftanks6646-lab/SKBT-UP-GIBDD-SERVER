"""Add FCM push tokens.

Revision ID: 0009_push_tokens
Revises: 0008_role_revoked_by
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009_push_tokens"
down_revision: str | None = "0008_role_revoked_by"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=4096), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_push_tokens_device_id", "push_tokens", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_push_tokens_device_id", table_name="push_tokens")
    op.drop_table("push_tokens")
