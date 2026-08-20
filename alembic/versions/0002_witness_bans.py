"""Add witness ban history.

Revision ID: 0002_witness_bans
Revises: 0001_initial_schema
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_witness_bans"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "witness_bans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("witness_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ban_level", sa.SmallInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("issued_by_employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.CheckConstraint("ban_level BETWEEN 1 AND 3", name="ck_witness_ban_level_history"),
        sa.ForeignKeyConstraint(["issued_by_employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["revoked_by_employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["witness_id"], ["witnesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_witness_active_ban",
        "witness_bans",
        ["witness_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_witness_active_ban", table_name="witness_bans")
    op.drop_table("witness_bans")
