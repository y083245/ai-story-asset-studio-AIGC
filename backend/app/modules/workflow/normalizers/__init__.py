"""Normalizers that turn provider JSON into stable analysis output shapes.

Split out of ``analysis_activities`` so each asset type's rules live next
to their tests, and the activity module stays focused on orchestration.
"""

from __future__ import annotations

from app.modules.workflow.normalizers.character import normalize_characters
from app.modules.workflow.normalizers.genre import normalize_genre
from app.modules.workflow.normalizers.prop import normalize_props
from app.modules.workflow.normalizers.scene import normalize_scenes

__all__ = [
    "normalize_characters",
    "normalize_genre",
    "normalize_props",
    "normalize_scenes",
]
