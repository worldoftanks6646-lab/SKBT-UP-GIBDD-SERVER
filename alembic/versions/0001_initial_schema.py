"""Create initial device registration and chat schema.

Revision ID: 0001_initial_schema
Revises: None
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


device_type = postgresql.ENUM("witness", "employee", name="device_type", create_type=False)
role_code = postgresql.ENUM(
    "inspector", "administrator", "chief", name="role_code", create_type=False
)
message_sender_type = postgresql.ENUM(
    "witness", "employee", name="message_sender_type", create_type=False
)
message_type = postgresql.ENUM(
    "text", "media", "geolocation", name="message_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    device_type.create(bind, checkfirst=True)
    role_code.create(bind, checkfirst=True)
    message_sender_type.create(bind, checkfirst=True)
    message_type.create(bind, checkfirst=True)

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("type", device_type, nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("app_version", sa.String(length=32), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devices_fingerprint_hash", "devices", ["fingerprint_hash"], unique=True)

    op.create_table(
        "witnesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ban_level", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ban_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("ban_level BETWEEN 0 AND 3", name="ck_witness_ban_level"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", role_code, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("witness_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["witness_id"], ["witnesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("witness_id"),
    )
    op.create_table(
        "role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_type", message_sender_type, nullable=False),
        sa.Column("message_type", message_type, nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_chat_id", "messages", ["chat_id"], unique=False)
    op.create_index("ix_messages_sender_device_id", "messages", ["sender_device_id"], unique=False)
    op.create_index("ix_messages_sent_at", "messages", ["sent_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_messages_sent_at", table_name="messages")
    op.drop_index("ix_messages_sender_device_id", table_name="messages")
    op.drop_index("ix_messages_chat_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("role_assignments")
    op.drop_table("chats")
    op.drop_table("roles")
    op.drop_table("employees")
    op.drop_table("witnesses")
    op.drop_index("ix_devices_fingerprint_hash", table_name="devices")
    op.drop_table("devices")

    bind = op.get_bind()
    message_type.drop(bind, checkfirst=True)
    message_sender_type.drop(bind, checkfirst=True)
    role_code.drop(bind, checkfirst=True)
    device_type.drop(bind, checkfirst=True)
