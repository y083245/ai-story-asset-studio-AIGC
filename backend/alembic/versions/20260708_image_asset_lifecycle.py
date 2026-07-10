"""Add image asset lifecycle fields.

Revision ID: 20260708_image_asset_lifecycle
Revises: 20260706_add_canonical_asset_ids
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260708_image_asset_lifecycle"
down_revision = "20260706_add_canonical_asset_ids"
branch_labels = None
depends_on = None

_TABLE_NAME = "image_assets"
_INDEX_NAMES = (
    "ix_image_assets_deleted_at",
    "ix_image_assets_purge_after",
    "ix_image_assets_expires_at",
    "ix_image_assets_delete_reason",
)


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(_TABLE_NAME)}


def _index_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(_TABLE_NAME)}


def upgrade() -> None:
    existing_columns = _column_names()

    if "deleted_at" not in existing_columns:
        op.add_column(
            _TABLE_NAME,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, comment="图片手动删除进入回收站的时间"),
        )
    if "deleted_by" not in existing_columns:
        op.add_column(
            _TABLE_NAME,
            sa.Column("deleted_by", sa.String(length=255), nullable=True, comment="执行删除的用户 ID"),
        )
    if "purge_after" not in existing_columns:
        op.add_column(
            _TABLE_NAME,
            sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True, comment="图片回收站自动清理时间"),
        )
    if "expires_at" not in existing_columns:
        op.add_column(
            _TABLE_NAME,
            sa.Column(
                "expires_at", sa.DateTime(timezone=True), nullable=True, comment="图片生成时间起满 6 个自然月的过期时间"
            ),
        )
    if "delete_reason" not in existing_columns:
        op.add_column(
            _TABLE_NAME,
            sa.Column(
                "delete_reason",
                sa.String(length=50),
                nullable=True,
                comment="图片进入回收站的原因: manual|retention_expired|project_purged",
            ),
        )

    existing_indexes = _index_names()
    if "ix_image_assets_deleted_at" not in existing_indexes:
        op.create_index("ix_image_assets_deleted_at", _TABLE_NAME, ["deleted_at"], unique=False)
    if "ix_image_assets_purge_after" not in existing_indexes:
        op.create_index("ix_image_assets_purge_after", _TABLE_NAME, ["purge_after"], unique=False)
    if "ix_image_assets_expires_at" not in existing_indexes:
        op.create_index("ix_image_assets_expires_at", _TABLE_NAME, ["expires_at"], unique=False)
    if "ix_image_assets_delete_reason" not in existing_indexes:
        op.create_index("ix_image_assets_delete_reason", _TABLE_NAME, ["delete_reason"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE image_assets
            SET expires_at = COALESCE(created_at, CURRENT_TIMESTAMP) + interval '6 months'
            WHERE expires_at IS NULL
            """
        )
    )


def downgrade() -> None:
    existing_indexes = _index_names()
    for index_name in _INDEX_NAMES:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=_TABLE_NAME)

    existing_columns = _column_names()
    for column_name in ("delete_reason", "expires_at", "purge_after", "deleted_by", "deleted_at"):
        if column_name in existing_columns:
            op.drop_column(_TABLE_NAME, column_name)
