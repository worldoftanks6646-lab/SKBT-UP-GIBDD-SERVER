"""Track active witness bans reliably.

Revision ID: 0011_active_ban_state
Revises: 0010_ban_expiry_notifications
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011_active_ban_state"
down_revision: str | None = "0010_ban_expiry_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_witness_active_ban", table_name="witness_bans")
    op.add_column(
        "witness_bans",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.execute(
        """
        UPDATE witness_bans
        SET is_active = false
        WHERE revoked_at IS NOT NULL
           OR (expires_at IS NOT NULL AND expires_at <= now())
        """
    )
    op.create_index(
        "uq_witness_active_ban",
        "witness_bans",
        ["witness_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_witness_active_ban", table_name="witness_bans")
    op.drop_column("witness_bans", "is_active")
    op.create_index(
        "uq_witness_active_ban",
        "witness_bans",
        ["witness_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
