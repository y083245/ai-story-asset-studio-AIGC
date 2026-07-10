"""Pydantic schemas for story reference data."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CharacterReference(BaseModel):
    character_id: str = Field(..., description="角色稳定 ID，如 CH_001")
    name: str = Field(default="", description="角色名称")
    role: str = Field(default="", description="角色定位")


class SceneReference(BaseModel):
    scene_id: str = Field(..., description="场景稳定 ID，如 SC_001")
    scene_name: str = Field(default="", description="场景名称")
    type: str = Field(default="", description="场景类型")


class PropReference(BaseModel):
    prop_id: str = Field(..., description="道具稳定 ID，如 PR_001")
    name: str = Field(default="", description="道具名称")
    importance: str = Field(default="", description="重要度")


class NegativePromptRule(BaseModel):
    rule: str = Field(..., description="负面提示词规则")
    applies_to: str = Field(default="image", description="适用范围")


class StoryBibleData(BaseModel):
    project_id: UUID
    version: int = Field(..., ge=1)
    title: str = ""
    genre: str = ""
    visual_style: str = ""
    aspect_ratio: str = "9:16"
    story_summary: str = ""
    main_conflict: str = ""
    emotional_tone: str = ""
    world_setting: str = ""
    time_period: str = ""
    color_palette: list[str] = Field(default_factory=list)
    composition_language: list[str] = Field(default_factory=list)
    characters: list[CharacterReference] = Field(default_factory=list)
    scenes: list[SceneReference] = Field(default_factory=list)
    props: list[PropReference] = Field(default_factory=list)
    negative_prompt_rules: list[NegativePromptRule] = Field(default_factory=list)


class StoryBibleBuildRequest(BaseModel):
    analysis_output: dict[str, object] | None = Field(default=None, description="分析工作流输出")


class StoryBiblePatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    genre: str | None = Field(default=None, max_length=100)
    visual_style: str | None = Field(default=None, max_length=200)
    aspect_ratio: str | None = Field(default=None, max_length=10)
    story_summary: str | None = None
    main_conflict: str | None = None
    emotional_tone: str | None = None
    world_setting: str | None = None
    time_period: str | None = Field(default=None, max_length=100)
    color_palette: list[str] | None = None
    composition_language: list[str] | None = None
    characters: list[CharacterReference] | None = None
    scenes: list[SceneReference] | None = None
    props: list[PropReference] | None = None
    negative_prompt_rules: list[NegativePromptRule] | None = None


class StoryBibleResponse(StoryBibleData):
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryBibleVersionItem(BaseModel):
    version: int
    created_at: datetime
    title: str = ""


class StoryBibleVersionListResponse(BaseModel):
    project_id: UUID
    versions: list[StoryBibleVersionItem]


class StoryBibleVersionSnapshot(BaseModel):
    project_id: UUID
    version: int
    created_at: datetime
    data: StoryBibleData


class ReferenceValidationError(BaseModel):
    entity_type: str
    missing_ids: list[str]


class StoryBibleErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool
    details: list[ReferenceValidationError] | None = None
