"""Track delivery of temporary ban expiry notifications.

Revision ID: 0010_ban_expiry_notifications
Revises: 0009_push_tokens
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0010_ban_expiry_notifications"
down_revision: str | None = "0009_push_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "witness_bans",
        sa.Column("expiry_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("witness_bans", "expiry_notified_at")
