"""Pydantic v2 request/response schemas for the Quality & Retry module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# =============================================================================
# Request schemas
# =============================================================================


class ImageQualityRequest(BaseModel):
    """Request to inspect a generated image asset."""

    project_id: uuid.UUID = Field(..., description="项目 ID")
    related_id: str | None = Field(None, min_length=1, max_length=20, description="关联实体 ID")
    asset_id: uuid.UUID = Field(..., description="被评估的 image_assets.id")
    generation_task_id: uuid.UUID | None = Field(None, description="关联的 image_generation_tasks.id")
    image_bytes: bytes | None = Field(None, description="图片二进制数据（如已缓存则可为空，service 会从 storage 拉取）")
    check_dimensions: list[str] = Field(
        default_factory=lambda: ["face", "outfit", "scene", "prop", "watermark", "body", "composition"],
        description="需要检查的维度列表",
    )
    prompt: str = Field(default="", max_length=12000, description="本轮生成使用的正向 prompt")
    negative_prompt: str = Field(default="", max_length=12000, description="本轮生成使用的反向 prompt")
    asset_bible: dict[str, object] | str | None = Field(None, description="故事资产圣经快照")
    style_keywords: list[str] = Field(default_factory=list, description="风格关键词")
    expected_props: list[str] = Field(default_factory=list, description="期望出现的道具")
    retry_history: list[dict[str, object]] = Field(default_factory=list, description="重试历史")

    model_config = {"extra": "forbid"}


class RetryExecuteRequest(BaseModel):
    """Request to execute a retry decision."""

    decision_id: uuid.UUID = Field(..., description="retry_decisions.id")
    project_id: uuid.UUID = Field(..., description="项目 ID")

    model_config = {"extra": "forbid"}


# =============================================================================
# Response schemas
# =============================================================================


class IssueItem(BaseModel):
    """A single quality issue detected during inspection."""

    code: str = Field(..., description="问题代码，如 FACE_CHANGED")
    dimension: str = Field(..., description="问题维度，如 face")
    description: str = Field(default="", description="问题描述")
    score: float | None = Field(None, description="该维度的评分")
    threshold: float | None = Field(None, description="阈值")
    severity: str = Field(default="warning", description="严重程度: warning | critical")


class QualityReportResponse(BaseModel):
    """Response for a quality inspection report."""

    report_id: uuid.UUID
    project_id: uuid.UUID
    related_id: str | None = None
    asset_id: uuid.UUID | None = None
    asset_type: str
    generation_task_id: uuid.UUID | None = None

    # Scores
    quality_score: float
    face_consistency_score: float | None = None
    outfit_consistency_score: float | None = None
    scene_consistency_score: float | None = None
    prop_presence_score: float | None = None
    composition_score: float | None = None

    # Issues
    issues: list[IssueItem] = Field(default_factory=list)

    # Decision
    retry_required: bool = False
    retry_prompt_patch: str | None = None
    needs_review: bool = False

    # Retry decision reference (if applicable)
    retry_decision_id: uuid.UUID | None = None

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RetryDecisionResponse(BaseModel):
    """Response for a retry decision."""

    decision_id: uuid.UUID
    project_id: uuid.UUID
    generation_task_id: uuid.UUID | None = None
    related_id: str | None = None
    asset_type: str

    # Counts
    retry_count: int = 0
    max_retries: int = 3
    max_auto_fixes: int = 2
    auto_fix_count: int = 0

    # Decision
    action: str
    retry_prompt_patch: str | None = None
    previous_prompt: str | None = None
    quality_report_id: uuid.UUID | None = None

    # Outcome
    outcome: str | None = None

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RetryExecuteResponse(BaseModel):
    """Response after executing a retry decision."""

    decision_id: uuid.UUID
    success: bool
    action: str
    message: str
    updated_task_retry_count: int | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="错误信息")
    detail: str | None = Field(None, description="详细描述")
    error_code: str | None = Field(None, description="错误码")
