"""Add canonical asset IDs for reference image chains.

Revision ID: 20260706_add_canonical_asset_ids
Revises: 20260705_expand_id_columns
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260706_add_canonical_asset_ids"
down_revision = "20260705_expand_id_columns"
branch_labels = None
depends_on = None

_TABLES: tuple[str, ...] = ("characters", "scenes", "props")


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    for table in _TABLES:
        if "canonical_asset_id" not in _column_names(table):
            op.add_column(
                table,
                sa.Column(
                    "canonical_asset_id",
                    sa.String(length=500),
                    nullable=True,
                    comment="Canonical reference asset storage_path/id",
                ),
            )


def downgrade() -> None:
    for table in _TABLES:
        if "canonical_asset_id" in _column_names(table):
            op.drop_column(table, "canonical_asset_id")
