"""Pydantic v2 request/response schemas for the Project module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.contracts.enums import AspectRatio, GenerationMode, ProjectStatus, StyleMode


class ProjectCreateRequest(BaseModel):
    """Payload for POST /api/projects."""

    title: str = Field(..., min_length=1, max_length=200, description="项目标题")
    aspect_ratio: AspectRatio = Field(default=AspectRatio.RATIO_9_16, description="资产画幅比")
    style_mode: StyleMode = Field(default=StyleMode.AUTO, description="风格模式")
    manual_style: str = Field(default="", max_length=500, description="手动指定的风格（仅 style_mode=manual 时有效）")
    generation_mode: GenerationMode = Field(default=GenerationMode.FAST_PREVIEW, description="生成模式")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped

    @field_validator("manual_style")
    @classmethod
    def manual_style_required_when_mode_manual(cls, v: str, info: Any) -> str:
        # Only enforce when style_mode is set to MANUAL
        if info.data and info.data.get("style_mode") == StyleMode.MANUAL and not v.strip():
            raise ValueError("manual_style is required when style_mode is 'manual'")
        return v


# ---- Response Models ----


class ProjectResponse(BaseModel):
    """Project detail returned by GET endpoints."""

    project_id: UUID
    user_id: str
    title: str
    status: ProjectStatus
    aspect_ratio: str
    style_mode: StyleMode
    manual_style: str
    generation_mode: GenerationMode
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    purge_after: datetime | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_project(cls, project: Any) -> ProjectResponse:
        """Build the public API shape from a Project ORM object or mapping."""
        return cls(
            project_id=_field(project, "project_id") or _field(project, "id"),
            user_id=_field(project, "user_id"),
            title=_field(project, "title"),
            status=_field(project, "status"),
            aspect_ratio=_field(project, "aspect_ratio"),
            style_mode=_field(project, "style_mode"),
            manual_style=_field(project, "manual_style", "") or "",
            generation_mode=_field(project, "generation_mode"),
            progress=_progress_percentage(_field(project, "progress_json")),
            created_at=_field(project, "created_at"),
            updated_at=_field(project, "updated_at"),
            deleted_at=_field(project, "deleted_at"),
            purge_after=_field(project, "purge_after"),
        )


def _field(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _progress_percentage(progress_json: Any) -> int:
    if not isinstance(progress_json, dict):
        return 0

    raw_value = progress_json.get("percentage", progress_json.get("progress", 0))
    if raw_value is None:
        return 0
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, value))


class ProjectListResponse(BaseModel):
    """Paginated project list."""

    items: list[ProjectResponse]
    total: int


class ProjectUpdateRequest(BaseModel):
    """Payload for PATCH /api/projects/{project_id}.

    All fields optional — only supplied fields are updated.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    aspect_ratio: AspectRatio | None = None
    style_mode: StyleMode | None = None
    manual_style: str | None = Field(default=None, max_length=500)
    generation_mode: GenerationMode | None = None
    status: ProjectStatus | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank_if_provided(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("title must not be blank")
        return v.strip() if v else v


class ProgressInfo(BaseModel):
    """Progress breakdown for aggregated status."""

    completed: int = 0
    total: int = 0
    percentage: int = 0


class ProjectStatusResponse(BaseModel):
    """Aggregated project status returned by GET .../status."""

    project_id: UUID
    current_stage: str
    progress: ProgressInfo
    message: str


class ProjectCopyResponse(BaseModel):
    """Response for POST /api/projects/{project_id}/copy."""

    original_id: UUID
    new_project: ProjectResponse


class ErrorDetail(BaseModel):
    """Standard error response body."""

    code: str
    message: str
    retryable: bool


class ErrorResponse(BaseModel):
    """Wrapper for error responses."""

    error: ErrorDetail
