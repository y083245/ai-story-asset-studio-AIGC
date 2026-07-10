"""M08 Scene Library Module.

Extracts, deduplicates, and manages reusable scene spaces across the
Story Asset Studio pipeline.  Scenes receive stable IDs (SC_001, SC_002, ...),
fixed-anchor lists, spatial-layer descriptions, composition-view rules,
and empty-scene prompts.

This module ONLY outputs scene settings and asset plans.
It does NOT generate images; scene images are produced by Image Asset.

Hard rules:
- scene_name must be at least 4 Chinese characters.
- Every scene must have at least 3 fixed_anchors.
- scene_prompt must NOT contain any character names.
- empty_scene_prompt must start with "不能出现其他人，无人纯场景，".
- Scene images must NOT contain people, text, watermarks, or logos.
"""

from __future__ import annotations

from app.modules.scene_library.models import GenerationTask, Scene, SceneVersion
from app.modules.scene_library.schemas import (
    CandidateSceneInput,
    ExtractedScene,
    ExtractedScenesRequest,
    ExtractedScenesResponse,
    GenerationTaskStatus,
    SceneListResponse,
    SceneRegenerateResponse,
    SceneResponse,
    SceneUpdateRequest,
)
from app.modules.scene_library.service import SceneLibraryService

__all__ = [
    "Scene",
    "SceneVersion",
    "GenerationTask",
    "CandidateSceneInput",
    "ExtractedScene",
    "ExtractedScenesRequest",
    "ExtractedScenesResponse",
    "GenerationTaskStatus",
    "SceneListResponse",
    "SceneRegenerateResponse",
    "SceneResponse",
    "SceneUpdateRequest",
    "SceneLibraryService",
]
