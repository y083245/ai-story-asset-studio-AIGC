"""Pydantic v2 request/response schemas for the M11 Image Asset module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

type ImageAssetCategory = Literal["character", "prop", "scene"]

# =============================================================================
# Request schemas
# =============================================================================


class GenerateAssetRequest(BaseModel):
    """Request to generate a single image asset."""

    project_id: uuid.UUID = Field(..., description="项目 ID")
    asset_type: str = Field(
        ...,
        pattern=(
            r"^(character_bible_sheet|character_front|character_turnaround|character_expression|"
            r"scene_empty|scene_with_atmosphere|prop_product|prop_usage)$"
        ),
        description="资产类型",
    )
    related_id: str | None = Field(
        None,
        min_length=1,
        max_length=20,
        description="关联实体 ID (CH_001/SC_001/PR_001)",
    )
    reference_asset_ids: list[str] = Field(default_factory=list, description="引用的其他 ImageAsset storage_path 列表")
    extra_constraints: str | None = Field(None, max_length=2000, description="额外的 prompt 约束文本")

    model_config = {"extra": "forbid"}


class ImagePromptPreviewResponse(BaseModel):
    """Prompt preview built through the same path as image generation."""

    prompt: str
    negative_prompt: str


class BatchGenerateRequest(BaseModel):
    """Request to generate multiple image assets for a project."""

    project_id: uuid.UUID = Field(..., description="项目 ID")
    requests: list[GenerateAssetRequest] = Field(..., min_length=1, max_length=50, description="批量生成请求列表")

    model_config = {"extra": "forbid"}


class GenerateJobResponse(BaseModel):
    """Response for an async generation job creation."""

    task_id: uuid.UUID
    project_id: uuid.UUID
    status: str = "pending"
    polling_url: str


class QualityCallback(BaseModel):
    """Callback from M13 Vision Quality module with quality assessment results."""

    generation_task_id: uuid.UUID = Field(..., description="关联的 image_generation_tasks.id")
    asset_id: uuid.UUID = Field(..., description="被评估的 image_assets.id")
    quality_status: str = Field(
        ...,
        pattern=r"^(pending|passed|needs_retry|needs_manual_review|failed|skipped)$",
        description="质检结果",
    )
    quality_report_id: str = Field(..., description="M13 质检报告 ID")
    issues: list[dict[str, Any]] = Field(default_factory=list, description="质检发现的问题列表")
    retry_prompt_patch: str | None = Field(None, description="M13 建议的 prompt 修补内容")

    model_config = {"extra": "forbid"}


class ImageAssetLibraryQuery(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    project_id: uuid.UUID | None = None
    category: ImageAssetCategory | None = None
    asset_type: str | None = None
    keyword: str | None = Field(None, max_length=100)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    model_config = {"extra": "forbid"}


class ImageAssetTrashQuery(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    project_id: uuid.UUID | None = None
    category: ImageAssetCategory | None = None
    asset_type: str | None = None
    keyword: str | None = Field(None, max_length=100)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    model_config = {"extra": "forbid"}


class ImageAssetBatchOperationRequest(BaseModel):
    asset_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)

    model_config = {"extra": "forbid"}


class ImageAssetPermanentDeleteRequest(BaseModel):
    asset_id: uuid.UUID
    reason: Literal["manual_permanent", "trash_expired", "retention_expired"]

    model_config = {"extra": "forbid"}


class ImageAssetBatchPermanentDeleteRequest(BaseModel):
    requests: list[ImageAssetPermanentDeleteRequest] = Field(..., min_length=1, max_length=100)

    model_config = {"extra": "forbid"}


# =============================================================================
# Response schemas
# =============================================================================


class ImageAssetResponse(BaseModel):
    """Response for a single image asset."""

    asset_id: uuid.UUID
    project_id: uuid.UUID
    asset_type: str
    related_id: str | None
    asset_url: str
    thumbnail_url: str | None = None
    storage_path: str
    prompt: str
    negative_prompt: str
    model_name: str
    provider_task_id: str | None = None
    generation_task_id: uuid.UUID | None = None
    width: int
    height: int
    reference_asset_ids: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> ImageAssetResponse:
        """Validate from an ORM model instance."""
        return cls(
            asset_id=obj.id,
            project_id=obj.project_id,
            asset_type=obj.asset_type,
            related_id=obj.related_id,
            asset_url=obj.asset_url,
            thumbnail_url=getattr(obj, "thumbnail_url", None),
            storage_path=obj.storage_path,
            prompt=obj.prompt,
            negative_prompt=obj.negative_prompt,
            model_name=obj.model_name,
            provider_task_id=getattr(obj, "provider_task_id", None),
            generation_task_id=getattr(obj, "generation_task_id", None),
            width=getattr(obj, "width", None) or 1080,
            height=getattr(obj, "height", None) or 1920,
            reference_asset_ids=getattr(obj, "reference_asset_ids", None) or [],
            status=obj.status,
            created_at=obj.created_at if hasattr(obj, "created_at") else None,
            updated_at=obj.updated_at if hasattr(obj, "updated_at") else None,
        )


class GenerationTaskResponse(BaseModel):
    """Response for a generation task."""

    task_id: uuid.UUID
    project_id: uuid.UUID
    asset_type: str
    related_id: str | None
    provider: str
    model_name: str
    status: str
    retry_count: int
    max_retries: int
    error_message: str | None
    quality_status: str | None
    quality_report_id: str | None
    asset_id: uuid.UUID | None = None
    storage_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> GenerationTaskResponse:
        """Validate from an ORM model instance."""
        return cls(
            task_id=obj.id,
            project_id=obj.project_id,
            asset_type=obj.asset_type,
            related_id=obj.related_id,
            provider=obj.provider,
            model_name=obj.model_name,
            status=obj.status,
            retry_count=getattr(obj, "retry_count", 0) or 0,
            max_retries=getattr(obj, "max_retries", 3) or 3,
            error_message=obj.error_message,
            quality_status=obj.quality_status,
            quality_report_id=obj.quality_report_id,
            asset_id=getattr(obj, "asset_id", None),
            storage_path=getattr(obj, "storage_path", None),
            created_at=obj.created_at if hasattr(obj, "created_at") else None,
            updated_at=obj.updated_at if hasattr(obj, "updated_at") else None,
        )


class ImageAssetAuditLogItem(BaseModel):
    audit_id: uuid.UUID
    project_id: uuid.UUID
    asset_id: uuid.UUID | None = None
    user_id: str
    action: str
    reason: str | None = None
    asset_type: str | None = None
    related_id: str | None = None
    storage_path_hash: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> ImageAssetAuditLogItem:
        return cls(
            audit_id=obj.id,
            project_id=obj.project_id,
            asset_id=obj.asset_id,
            user_id=obj.user_id,
            action=obj.action,
            reason=obj.reason,
            asset_type=obj.asset_type,
            related_id=obj.related_id,
            storage_path_hash=obj.storage_path_hash,
            details=getattr(obj, "details", None) or {},
            created_at=obj.created_at,
        )


class ImageAssetAuditLogResponse(BaseModel):
    items: list[ImageAssetAuditLogItem]
    total: int
    page: int
    page_size: int


class ImageAssetLibraryItem(BaseModel):
    asset_id: uuid.UUID
    display_name: str
    project_id: uuid.UUID
    project_title: str
    project_status: str
    project_deleted_at: datetime | None
    category: ImageAssetCategory
    asset_type: str
    asset_type_label: str
    related_id: str | None
    related_name: str | None
    asset_url: str
    thumbnail_url: str | None
    storage_path: str
    prompt_summary: str
    prompt: str
    model_name: str
    status: str
    quality_status: str | None
    width: int
    height: int
    created_at: datetime
    expires_at: datetime
    remaining_retention_days: int
    is_expiring_soon: bool


class ImageAssetProjectOption(BaseModel):
    project_id: uuid.UUID
    project_title: str
    project_status: str
    project_deleted_at: datetime | None
    is_project_in_trash: bool
    total: int


class ImageAssetProjectGroup(BaseModel):
    project_id: uuid.UUID
    project_title: str
    project_status: str
    project_deleted_at: datetime | None
    is_project_in_trash: bool
    total: int
    latest_created_at: datetime
    categories: dict[ImageAssetCategory, list[ImageAssetLibraryItem]]


class ImageAssetDateGroup(BaseModel):
    date: date
    total: int
    project_count: int
    projects: list[ImageAssetProjectGroup]


class ImageAssetLibraryResponse(BaseModel):
    groups: list[ImageAssetDateGroup]
    available_projects: list[ImageAssetProjectOption] = Field(default_factory=list)
    page: int
    page_size: int
    total: int


class ImageAssetTrashItem(BaseModel):
    asset_id: uuid.UUID
    display_name: str
    project_id: uuid.UUID
    project_title: str
    project_status: str
    project_deleted_at: datetime | None
    category: ImageAssetCategory
    asset_type: str
    asset_type_label: str
    related_id: str | None
    related_name: str | None
    asset_url: str
    thumbnail_url: str | None
    prompt_summary: str
    prompt: str
    model_name: str
    status: str
    quality_status: str | None
    created_at: datetime
    deleted_at: datetime
    purge_after: datetime | None
    expires_at: datetime
    remaining_cleanup_days: int
    can_restore: bool


class ImageAssetTrashResponse(BaseModel):
    items: list[ImageAssetTrashItem]
    available_projects: list[ImageAssetProjectOption] = Field(default_factory=list)
    page: int
    page_size: int
    total: int


class ImageAssetOperationResult(BaseModel):
    asset_id: uuid.UUID
    status: Literal["success", "failed"]
    code: str
    message: str


class ImageAssetBatchOperationResponse(BaseModel):
    results: list[ImageAssetOperationResult]
    total: int
    succeeded: int
    failed: int


class BatchGenerateResponse(BaseModel):
    """Response for a batch generation request."""

    project_id: uuid.UUID
    results: list[ImageAssetResponse]
    total: int
    succeeded: int
    failed: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    code: str
    message: str
    retryable: bool = False
