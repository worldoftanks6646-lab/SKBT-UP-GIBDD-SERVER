"""Add role assignment history.

Revision ID: 0003_role_history
Revises: 0002_witness_bans
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_role_history"
down_revision: str | None = "0002_witness_bans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "role_assignments_employee_id_key", "role_assignments", type_="unique"
    )
    op.add_column(
        "role_assignments",
        sa.Column(
            "assigned_by_employee_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column(
        "role_assignments",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_role_assignments_assigned_by_employee",
        "role_assignments",
        "employees",
        ["assigned_by_employee_id"],
        ["id"],
    )
    op.create_index(
        "uq_employee_active_role",
        "role_assignments",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.execute(
        """
        INSERT INTO roles (id, code, name, description) VALUES
            ('10000000-0000-0000-0000-000000000001', 'inspector', 'Инспектор', NULL),
            ('10000000-0000-0000-0000-000000000002', 'administrator', 'Администратор', NULL),
            ('10000000-0000-0000-0000-000000000003', 'chief', 'Начальник', NULL)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("uq_employee_active_role", table_name="role_assignments")
    op.drop_constraint(
        "fk_role_assignments_assigned_by_employee",
        "role_assignments",
        type_="foreignkey",
    )
    op.drop_column("role_assignments", "revoked_at")
    op.drop_column("role_assignments", "assigned_by_employee_id")
    op.create_unique_constraint(
        "role_assignments_employee_id_key", "role_assignments", ["employee_id"]
    )
