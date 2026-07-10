"""M09 Prop Library Module.

Extracts, deduplicates, and manages prop profiles across the
Story Engine pipeline.  Props receive stable IDs (PR_001, PR_002, ...),
state timelines, singleton-image plans, and usage-image plans.

This module ONLY outputs prop settings and asset plans.
It does NOT generate images — image assets are produced by M11 Image Asset.
Shots reference props by prop_id; they MUST NOT invent props on the fly.
"""

from __future__ import annotations

from app.modules.prop_library.models import GenerationTask, Prop, PropVersion
from app.modules.prop_library.schemas import (
    ExtractedProp,
    ExtractedPropsRequest,
    ExtractedPropsResponse,
    PropListResponse,
    PropRegenerateResponse,
    PropResponse,
    PropUpdateRequest,
    StateTimelineItem,
)
from app.modules.prop_library.service import PropLibraryService

__all__ = [
    "Prop",
    "PropVersion",
    "GenerationTask",
    "StateTimelineItem",
    "ExtractedProp",
    "ExtractedPropsRequest",
    "ExtractedPropsResponse",
    "PropListResponse",
    "PropRegenerateResponse",
    "PropResponse",
    "PropUpdateRequest",
    "PropLibraryService",
]
