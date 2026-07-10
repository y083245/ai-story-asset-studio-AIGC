"""Backfill image asset expires_at for post-lifecycle generated assets.

Revision ID: 20260709_backfill_asset_expiry
Revises: 20260708_image_asset_audit_logs
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260709_backfill_asset_expiry"
down_revision = "20260708_image_asset_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    pass
