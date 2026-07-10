"""Pydantic v2 request/response schemas for the Character Library module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Shared sub-models
# =============================================================================


class ReferenceImagePlanItem(BaseModel):
    """A single entry in the reference-image plan."""

    category: str = Field(..., min_length=1, description="类别，如「正面半身」")
    description: str = Field(..., min_length=1, description="图像描述 prompt")
    priority: str = Field(default="required", description="required / optional")


class Relationship(BaseModel):
    """Relationship to another character."""

    character_id: str = Field(..., description="关联角色 ID (CH_xxx)")
    relation: str = Field(..., description="关系描述，如「恋人」「上司」")


class ExtractedCharacter(BaseModel):
    """A single extracted character after deduplication and enrichment."""

    character_id: str = Field(..., description="CH_xxx")
    name: str
    aliases: list[str] = Field(default_factory=list)
    role_type: str = "配角"

    # Physical
    gender: str | None = None
    age: str | None = None
    height: str | None = None
    body_type: str | None = None
    face_shape: str | None = None
    facial_bone_structure: str | None = None
    skin_tone: str | None = None
    eyes: str | None = None
    eyebrows: str | None = None
    nose: str | None = None
    mouth: str | None = None
    hair_color: str | None = None
    hair_style: str | None = None

    # Clothing
    default_outfit: str | None = None
    outfit_details: str | None = None
    shoes: str | None = None
    accessories: str | None = None

    # Traits
    identity: str | None = None
    personality: str | None = None
    relationship_to_others: list[Relationship] = Field(default_factory=list)
    first_appearance: str | None = None
    emotion_pack: list[str] = Field(default_factory=list)

    # Consistency
    consistency_tag: str | None = None
    forbidden_changes: list[str] = Field(default_factory=list)
    reference_image_plan: list[ReferenceImagePlanItem] = Field(default_factory=list)
    reference_assets: list[str] = Field(default_factory=list)


# =============================================================================
# Request schemas
# =============================================================================


class CandidateCharacterInput(BaseModel):
    """Input from M05 Text Understanding — a raw candidate character."""

    name: str
    role: str = "配角"
    traits: list[str] = Field(default_factory=list)
    description: str = ""
    first_appearance: str = ""


class ExtractedCharactersRequest(BaseModel):
    """Request to extract and formalise characters from M05 candidates."""

    project_id: str = Field(..., min_length=1, description="项目 ID (uuid string)")
    candidates: list[CandidateCharacterInput] = Field(..., min_length=1, description="M05 输出的候选角色列表")


class CharacterUpdateRequest(BaseModel):
    """Payload for PATCH /api/projects/{project_id}/characters/{character_id}.

    All fields optional — only supplied fields are updated.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    aliases: list[str] | None = None
    role_type: str | None = None
    sort_order: int | None = Field(default=None, ge=0)

    # Physical
    gender: str | None = None
    age: str | None = None
    height: str | None = None
    body_type: str | None = None
    face_shape: str | None = None
    facial_bone_structure: str | None = None
    skin_tone: str | None = None
    eyes: str | None = None
    eyebrows: str | None = None
    nose: str | None = None
    mouth: str | None = None
    hair_color: str | None = None
    hair_style: str | None = None

    # Clothing
    default_outfit: str | None = None
    outfit_details: str | None = None
    shoes: str | None = None
    accessories: str | None = None

    # Traits
    identity: str | None = None
    personality: str | None = None
    relationship_to_others: list[dict[str, str]] | None = None
    first_appearance: str | None = None
    emotion_pack: list[str] | None = None

    # Consistency
    consistency_tag: str | None = None
    forbidden_changes: list[str] | None = None
    reference_image_plan: list[dict[str, str]] | None = None
    canonical_asset_id: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_not_blank_if_provided(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v.strip() if v else v


# =============================================================================
# Response schemas
# =============================================================================


class CharacterResponse(BaseModel):
    """Character detail returned by GET endpoints."""

    id: UUID
    project_id: UUID
    character_id: str
    name: str
    aliases: list[str] | None = None
    role_type: str
    sort_order: int

    gender: str | None = None
    age: str | None = None
    height: str | None = None
    body_type: str | None = None
    face_shape: str | None = None
    facial_bone_structure: str | None = None
    skin_tone: str | None = None
    eyes: str | None = None
    eyebrows: str | None = None
    nose: str | None = None
    mouth: str | None = None
    hair_color: str | None = None
    hair_style: str | None = None

    default_outfit: str | None = None
    outfit_details: str | None = None
    shoes: str | None = None
    accessories: str | None = None

    identity: str | None = None
    personality: str | None = None
    relationship_to_others: list[dict[str, str]] | None = None
    first_appearance: str | None = None
    emotion_pack: list[str] | None = None

    consistency_tag: str | None = None
    forbidden_changes: list[str] | None = None
    reference_image_plan: list[dict[str, str]] | None = None
    canonical_asset_id: str | None = None
    reference_assets: list[str] | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CharacterListResponse(BaseModel):
    """List of characters for a project."""

    project_id: UUID
    characters: list[CharacterResponse]
    total: int


class ExtractedCharactersResponse(BaseModel):
    """Response after character extraction and formalisation."""

    project_id: str
    characters: list[ExtractedCharacter]
    merged_count: int = Field(default=0, description="合并的候选角色数量（去重计数）")
    total_candidates: int = Field(default=0, description="输入的候选角色总数")


class GenerationTaskStatus(BaseModel):
    """Status of a regeneration task."""

    task_id: UUID
    status: str
    character_id: str


class CharacterRegenerateResponse(BaseModel):
    """Response from POST .../regenerate."""

    task_id: UUID
    character_id: str
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
