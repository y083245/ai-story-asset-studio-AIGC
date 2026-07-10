"""M07 Character Library Module.

Extracts, deduplicates, and manages character profiles across the
Story Engine pipeline.  Characters receive stable IDs (CH_001, CH_002, ...),
consistency tags, forbidden-change lists, and reference-image plans.

This module ONLY outputs character settings and reference plans.
It does NOT generate images — image assets are produced by M11 Image Asset.
Shots reference characters by character_id; they MUST NOT invent characters
on the fly.
"""

from __future__ import annotations

from app.modules.character_library.models import Character, CharacterVersion
from app.modules.character_library.schemas import (
    CharacterListResponse,
    CharacterRegenerateResponse,
    CharacterResponse,
    CharacterUpdateRequest,
    ExtractedCharactersRequest,
    ExtractedCharactersResponse,
    GenerationTaskStatus,
    ReferenceImagePlanItem,
)
from app.modules.character_library.service import CharacterLibraryService

__all__ = [
    "Character",
    "CharacterVersion",
    "CharacterListResponse",
    "CharacterRegenerateResponse",
    "CharacterResponse",
    "CharacterUpdateRequest",
    "ExtractedCharactersRequest",
    "ExtractedCharactersResponse",
    "GenerationTaskStatus",
    "ReferenceImagePlanItem",
    "CharacterLibraryService",
]
