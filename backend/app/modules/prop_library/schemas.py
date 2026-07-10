"""Pydantic v2 request/response schemas for the Prop Library module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Shared sub-models
# =============================================================================


class StateTimelineItem(BaseModel):
    """A single entry in the prop state timeline."""

    step_index: int = Field(..., ge=1, description="状态序号，从1开始")
    state: str = Field(..., min_length=1, description="道具在此节点的状态简述")
    description: str = Field(default="", description="状态变化的详细描述")


class ExtractedProp(BaseModel):
    """A single extracted prop after deduplication and enrichment."""

    prop_id: str = Field(..., description="PR_xxx")
    name: str
    aliases: list[str] = Field(default_factory=list)
    importance: str = Field(default="minor", description="core|supporting|minor")
    category: str | None = None
    owner_character_id: str | None = None

    # Physical description
    visual_features: str | None = None
    material: str | None = None
    color: str | None = None
    size: str | None = None

    # Story context
    first_appearance: str | None = None
    plot_function: str | None = None

    # State timeline
    state_timeline: list[StateTimelineItem] = Field(default_factory=list)

    # Prompts
    prop_prompt: str | None = None
    usage_prompt: str | None = None

    # Assets
    reference_assets: list[str] = Field(default_factory=list)


# =============================================================================
# Request schemas
# =============================================================================


class CandidatePropInput(BaseModel):
    """Input from M05 Text Understanding — a raw candidate prop."""

    name: str = Field(..., min_length=1, description="道具名称")
    description: str = Field(default="", description="道具描述")
    aliases: list[str] = Field(default_factory=list, description="已知别名")
    owner_name: str = Field(default="", description="所属角色名称 (非角色ID)")
    first_appearance: str = Field(default="", description="首次出场描述")
    function_hint: str = Field(default="", description="剧情功能提示")


class ExtractedPropsRequest(BaseModel):
    """Request to extract and formalise props from M05 candidates."""

    project_id: str = Field(..., min_length=1, description="项目 ID (uuid string)")
    candidates: list[CandidatePropInput] = Field(..., min_length=1, description="M05 输出的候选道具列表")
    character_ids: list[str] = Field(default_factory=list, description="该项目中已知的角色 ID 列表，用于 owner 校验")
    chapter_text: list[str] = Field(default_factory=list, description="章节文本，用于状态时间线推导")


class PropUpdateRequest(BaseModel):
    """Payload for PATCH /api/projects/{project_id}/props/{prop_id}.

    All fields optional — only supplied fields are updated.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    aliases: list[str] | None = None
    importance: str | None = None
    category: str | None = None
    owner_character_id: str | None = None
    visual_features: str | None = None
    material: str | None = None
    color: str | None = None
    size: str | None = None
    first_appearance: str | None = None
    plot_function: str | None = None
    state_timeline: list[dict[str, object]] | None = None
    prop_prompt: str | None = None
    usage_prompt: str | None = None
    canonical_asset_id: str | None = Field(default=None, max_length=500)
    reference_assets: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank_if_provided(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v.strip() if v else v

    @field_validator("importance")
    @classmethod
    def importance_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in ("core", "supporting", "minor"):
            raise ValueError("importance must be one of: core, supporting, minor")
        return v


# =============================================================================
# Response schemas
# =============================================================================


class PropResponse(BaseModel):
    """Prop detail returned by GET endpoints."""

    id: UUID
    project_id: UUID
    prop_id: str
    name: str
    aliases: list[str] | None = None
    importance: str
    category: str | None = None
    owner_character_id: str | None = None

    visual_features: str | None = None
    material: str | None = None
    color: str | None = None
    size: str | None = None

    first_appearance: str | None = None
    plot_function: str | None = None

    state_timeline: list[dict[str, object]] | None = None

    prop_prompt: str | None = None
    usage_prompt: str | None = None

    canonical_asset_id: str | None = None
    reference_assets: list[str] | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PropListResponse(BaseModel):
    """List of props for a project."""

    project_id: UUID
    props: list[PropResponse]
    total: int


class ExtractedPropsResponse(BaseModel):
    """Response after prop extraction and formalisation."""

    project_id: str
    props: list[ExtractedProp]
    merged_count: int = Field(default=0, description="合并的候选道具数量（去重计数）")
    total_candidates: int = Field(default=0, description="输入的候选道具总数")
    blocking_errors: list[str] = Field(default_factory=list, description="阻塞性错误（core 道具缺状态时间线等）")


class PropRegenerateResponse(BaseModel):
    """Response from POST .../regenerate."""

    task_id: UUID
    prop_id: str
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
