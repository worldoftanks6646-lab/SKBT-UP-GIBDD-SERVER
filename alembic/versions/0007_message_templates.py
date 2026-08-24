"""Add predefined employee message templates.

Revision ID: 0007_message_templates
Revises: 0006_notifications
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_message_templates"
down_revision: str | None = "0006_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "message_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": "10000000-0000-0000-0000-000000000001",
                "code": "accepted",
                "text": "Ваше сообщение принято.",
                "is_active": True,
            },
            {
                "id": "10000000-0000-0000-0000-000000000002",
                "code": "need_details",
                "text": "Пожалуйста, уточните обстоятельства происшествия.",
                "is_active": True,
            },
            {
                "id": "10000000-0000-0000-0000-000000000003",
                "code": "send_media",
                "text": "Пожалуйста, приложите фото или видео.",
                "is_active": True,
            },
            {
                "id": "10000000-0000-0000-0000-000000000004",
                "code": "send_location",
                "text": "Пожалуйста, отправьте геопозицию.",
                "is_active": True,
            },
            {
                "id": "10000000-0000-0000-0000-000000000005",
                "code": "completed",
                "text": "Обращение обработано. Спасибо за информацию.",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("message_templates")
