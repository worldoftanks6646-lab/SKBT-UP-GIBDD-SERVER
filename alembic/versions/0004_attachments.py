"""Add media attachments.

Revision ID: 0004_attachments
Revises: 0003_role_history
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_attachments"
down_revision: str | None = "0003_role_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


media_type = postgresql.ENUM("photo", "video", "gif", name="media_type", create_type=False)


def upgrade() -> None:
    media_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_type", media_type, nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_attachments_message_id", "attachments", ["message_id"])
    op.create_index("ix_attachments_expires_at", "attachments", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_attachments_expires_at", table_name="attachments")
    op.drop_index("ix_attachments_message_id", table_name="attachments")
    op.drop_table("attachments")
    media_type.drop(op.get_bind(), checkfirst=True)
