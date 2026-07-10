"""Pydantic v2 request/response schemas for the Scene Library module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Shared sub-models
# =============================================================================


class CandidateSceneInput(BaseModel):
    """Input from M05 Text Understanding — a raw candidate scene."""

    name: str = Field(..., min_length=1, description="场景名称")
    time: str = Field(default="", description="时段")
    description: str = Field(default="", description="场景描述")
    anchors: list[str] = Field(default_factory=list, description="场景锚点（关键视觉元素）")


class ExtractedScene(BaseModel):
    """A single extracted scene after deduplication and enrichment."""

    scene_id: str = Field(..., description="SC_xxx")
    scene_name: str
    scene_type: str = "室内"
    time_of_day: str | None = None
    weather: str | None = None
    lighting: str | None = None
    mood: str | None = None
    color_palette: list[str] = Field(default_factory=list)
    fixed_anchors: list[str] = Field(default_factory=list)
    foreground_elements: list[str] = Field(default_factory=list)
    midground_elements: list[str] = Field(default_factory=list)
    background_elements: list[str] = Field(default_factory=list)
    composition_views: list[str] = Field(default_factory=list)
    forbidden_elements: list[str] = Field(default_factory=list)
    scene_prompt: str | None = None
    empty_scene_prompt: str | None = None
    reference_assets: list[str] = Field(default_factory=list)


# =============================================================================
# Request schemas
# =============================================================================


class ExtractedScenesRequest(BaseModel):
    """Request to extract and formalise scenes from M05 candidates."""

    project_id: str = Field(..., min_length=1, description="项目 ID (uuid string)")
    candidates: list[CandidateSceneInput] = Field(..., min_length=1, description="M05 输出的候选场景列表")


class SceneUpdateRequest(BaseModel):
    """Payload for PATCH /api/projects/{project_id}/scenes/{scene_id}.

    All fields optional — only supplied fields are updated.
    """

    scene_name: str | None = Field(default=None, min_length=1, max_length=100)
    scene_type: str | None = None
    sort_order: int | None = Field(default=None, ge=0)
    time_of_day: str | None = None
    weather: str | None = None
    lighting: str | None = None
    mood: str | None = None
    color_palette: list[str] | None = None
    fixed_anchors: list[str] | None = None
    foreground_elements: list[str] | None = None
    midground_elements: list[str] | None = None
    background_elements: list[str] | None = None
    composition_views: list[str] | None = None
    forbidden_elements: list[str] | None = None
    scene_prompt: str | None = None
    empty_scene_prompt: str | None = None
    canonical_asset_id: str | None = Field(default=None, max_length=500)
    reference_assets: list[str] | None = None

    @field_validator("scene_name")
    @classmethod
    def name_not_blank_if_provided(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("scene_name must not be blank")
        return v.strip() if v else v


# =============================================================================
# Response schemas
# =============================================================================


class SceneResponse(BaseModel):
    """Scene detail returned by GET endpoints."""

    id: UUID
    project_id: UUID
    scene_id: str
    scene_name: str
    scene_type: str
    sort_order: int

    time_of_day: str | None = None
    weather: str | None = None
    lighting: str | None = None
    mood: str | None = None
    color_palette: list[str] | None = None

    fixed_anchors: list[str] = Field(default_factory=list)
    foreground_elements: list[str] | None = None
    midground_elements: list[str] | None = None
    background_elements: list[str] | None = None

    composition_views: list[str] | None = None
    forbidden_elements: list[str] | None = None

    scene_prompt: str | None = None
    empty_scene_prompt: str | None = None
    consistency_score: float | None = None

    canonical_asset_id: str | None = None
    reference_assets: list[str] | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SceneListResponse(BaseModel):
    """List of scenes for a project."""

    project_id: UUID
    scenes: list[SceneResponse]
    total: int


class ExtractedScenesResponse(BaseModel):
    """Response after scene extraction and formalisation."""

    project_id: str
    scenes: list[ExtractedScene]
    merged_count: int = Field(default=0, description="合并的候选场景数量（去重计数）")
    total_candidates: int = Field(default=0, description="输入的候选场景总数")


class GenerationTaskStatus(BaseModel):
    """Status of a regeneration task."""

    task_id: UUID
    status: str
    scene_id: str


class SceneRegenerateResponse(BaseModel):
    """Response from POST .../regenerate."""

    task_id: UUID
    scene_id: str
    status: str = "pending"


# =============================================================================
# Error models
# =============================================================================


class ErrorDetail(BaseModel):
    """Standard error response body."""

    code: str
    message: str
    retryable: bool


class ErrorResponse(BaseModel):
    """Wrapper for error responses."""

    error: ErrorDetail
