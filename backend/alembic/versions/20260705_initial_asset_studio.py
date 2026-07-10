"""Initial asset-only schema for Story Asset Studio.

Revision ID: 20260705_initial_asset_studio
Revises:
Create Date: 2026-07-05
"""

from __future__ import annotations

from importlib import import_module

from alembic import op
from app.db.base import Base

revision = "20260705_initial_asset_studio"
down_revision = None
branch_labels = None
depends_on = None

MODEL_MODULES = (
    "app.modules.character_library.models",
    "app.modules.image_asset.models",
    "app.modules.novel_intake.models",
    "app.modules.project.models",
    "app.modules.prop_library.models",
    "app.modules.quality_retry.models",
    "app.modules.scene_library.models",
    "app.modules.story_bible.models",
    "app.modules.workflow.models",
)


def _load_models() -> None:
    for module in MODEL_MODULES:
        import_module(module)


def upgrade() -> None:
    _load_models()
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    _load_models()
    Base.metadata.drop_all(bind=op.get_bind())
