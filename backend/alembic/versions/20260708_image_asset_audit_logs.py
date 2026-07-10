"""Add persisted image asset audit logs.

Revision ID: 20260708_image_asset_audit_logs
Revises: 20260708_image_asset_lifecycle
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260708_image_asset_audit_logs"
down_revision = "20260708_image_asset_lifecycle"
branch_labels = None
depends_on = None

_TABLE_NAME = "image_asset_audit_logs"
_INDEX_NAMES = (
    "ix_image_asset_audit_logs_project_id",
    "ix_image_asset_audit_logs_asset_id",
    "ix_image_asset_audit_logs_user_id",
    "ix_image_asset_audit_logs_action",
    "ix_image_asset_audit_logs_created_at",
)


def _table_exists() -> bool:
    inspector = sa.inspect(op.get_bind())
    return _TABLE_NAME in inspector.get_table_names()


def _index_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(_TABLE_NAME)} if _table_exists() else set()


def upgrade() -> None:
    if not _table_exists():
        op.create_table(
            _TABLE_NAME,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("user_id", sa.String(length=255), nullable=False),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("reason", sa.String(length=80), nullable=True),
            sa.Column("asset_type", sa.String(length=30), nullable=True),
            sa.Column("related_id", sa.String(length=50), nullable=True),
            sa.Column("storage_path_hash", sa.String(length=64), nullable=True),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = _index_names()
    if "ix_image_asset_audit_logs_project_id" not in existing_indexes:
        op.create_index("ix_image_asset_audit_logs_project_id", _TABLE_NAME, ["project_id"], unique=False)
    if "ix_image_asset_audit_logs_asset_id" not in existing_indexes:
        op.create_index("ix_image_asset_audit_logs_asset_id", _TABLE_NAME, ["asset_id"], unique=False)
    if "ix_image_asset_audit_logs_user_id" not in existing_indexes:
        op.create_index("ix_image_asset_audit_logs_user_id", _TABLE_NAME, ["user_id"], unique=False)
    if "ix_image_asset_audit_logs_action" not in existing_indexes:
        op.create_index("ix_image_asset_audit_logs_action", _TABLE_NAME, ["action"], unique=False)
    if "ix_image_asset_audit_logs_created_at" not in existing_indexes:
        op.create_index("ix_image_asset_audit_logs_created_at", _TABLE_NAME, ["created_at"], unique=False)


def downgrade() -> None:
    existing_indexes = _index_names()
    for index_name in _INDEX_NAMES:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=_TABLE_NAME)

    if _table_exists():
        op.drop_table(_TABLE_NAME)
