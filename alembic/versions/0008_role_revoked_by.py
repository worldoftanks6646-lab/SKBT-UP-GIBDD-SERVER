"""Store the employee who revoked a role.

Revision ID: 0008_role_revoked_by
Revises: 0007_message_templates
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0008_role_revoked_by"
down_revision: str | None = "0007_message_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "role_assignments",
        sa.Column("revoked_by_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_role_assignments_revoked_by_employee_id",
        "role_assignments",
        "employees",
        ["revoked_by_employee_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_role_assignments_revoked_by_employee_id",
        "role_assignments",
        type_="foreignkey",
    )
    op.drop_column("role_assignments", "revoked_by_employee_id")
