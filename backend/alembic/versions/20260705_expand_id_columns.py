"""Expand character/scene/prop ID columns to accommodate AI-generated IDs.

Revision ID: 20260705_expand_id_columns
Revises: 20260705_initial_asset_studio
Create Date: 2026-07-05
"""

from __future__ import annotations

from sqlalchemy import VARCHAR

from alembic import op

revision = "20260705_expand_id_columns"
down_revision = "20260705_initial_asset_studio"
branch_labels = None
depends_on = None

# Columns that change from VARCHAR(20) → VARCHAR(50).
# List of (table, column) pairs.
_ID_COLUMNS: list[tuple[str, str]] = [
    # Character IDs
    ("characters", "character_id"),
    ("character_versions", "character_id"),
    ("generation_tasks", "target_id"),
    # Scene IDs
    ("scenes", "scene_id"),
    ("scene_versions", "scene_id"),
    ("scene_generation_tasks", "target_id"),
    # Prop IDs
    ("props", "prop_id"),
    ("props", "owner_character_id"),
    ("prop_versions", "prop_id"),
    ("prop_generation_tasks", "target_id"),
    # Cross-references
    ("image_assets", "related_id"),
    ("image_generation_tasks", "related_id"),
    ("quality_reports", "related_id"),
    ("retry_decisions", "related_id"),
]


def upgrade() -> None:
    for table, column in _ID_COLUMNS:
        op.alter_column(table, column, type_=VARCHAR(50), existing_type=VARCHAR(20))


def downgrade() -> None:
    # Trim data that exceeds 20 chars before shrinking back — silent best-effort.
    for table, column in _ID_COLUMNS:
        op.execute(
            f"UPDATE {table} SET {column} = LEFT({column}, 20) WHERE LENGTH({column}) > 20"
        )
        op.alter_column(table, column, type_=VARCHAR(20), existing_type=VARCHAR(50))
