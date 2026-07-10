"""SQLAlchemy ORM models for the Image Asset module.

Exclusive write ownership:
- image_assets
- image_generation_tasks

Read-only references:
- Character, Scene, and Prop tables (never written by this module)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ImageAsset(Base, UUIDMixin, TimestampMixin):
    """Image asset record — one row per generated / uploaded image.

    Each asset is produced by a generation task (or uploaded
    externally) and stored via the Storage module.
    """

    __tablename__ = "image_assets"

    # ---- Identity ----
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    asset_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment=(
            "资产类型: character_bible_sheet|character_front|character_turnaround|character_expression|"
            "scene_empty|scene_with_atmosphere|prop_product|prop_usage"
        ),
    )
    related_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True, comment="关联实体 ID: CH_001/SC_001/PR_001"
    )

    # ---- Storage ----
    asset_url: Mapped[str] = mapped_column(String(500), nullable=False, comment="StorageService 返回的可访问 URL")
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="缩略图 URL")
    storage_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="StorageService 返回的 canonical asset_id"
    )

    # ---- Generation metadata ----
    prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="生成使用的正向提示词")
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="生成使用的反向提示词")
    model_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="使用的模型: seedream | fake-seedream")
    provider_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="Provider 返回的任务 ID")
    generation_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="关联的 image_generation_tasks.id"
    )

    # ---- Image dimensions ----
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1080, comment="图片宽度")
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1920, comment="图片高度")

    # ---- References to other assets ----
    reference_asset_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, comment="引用的其他 ImageAsset storage_path 列表"
    )

    # ---- Status ----
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="状态: pending|generating|completed|failed|retrying",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="图片手动删除进入回收站的时间",
    )
    deleted_by: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="执行删除的用户 ID")
    purge_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="图片回收站自动清理时间",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="图片生成时间起满 6 个自然月的过期时间",
    )
    delete_reason: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="图片进入回收站的原因: manual|retention_expired|project_purged",
    )

    def __repr__(self) -> str:
        return f"<ImageAsset id={self.id!r} type={self.asset_type!r} status={self.status!r}>"


class ImageGenerationTask(Base, UUIDMixin, TimestampMixin):
    """Image generation task record — tracks each provider call.

    Stores the full request/response payload for auditability and retry.
    """

    __tablename__ = "image_generation_tasks"

    # ---- Identity ----
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False, comment="要生成的资产类型")
    related_id: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="关联实体 ID")

    # ---- Provider info ----
    provider: Mapped[str] = mapped_column(String(50), nullable=False, comment="provider 名称: seedream | fake-seedream")
    model_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="模型名称")

    # ---- Payloads ----
    request_json: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, comment="ImageGenerationRequest 的 dict 表示"
    )
    response_json: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True, comment="ImageGenerationResponse 的 dict 表示"
    )

    # ---- Status ----
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="任务状态: pending|running|success|failed|retrying|cancelled",
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已重试次数")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, comment="最大重试次数")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    # ---- Quality (write-back from M13) ----
    quality_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="质检状态 (由 M13 回填): pending|passed|needs_retry|needs_manual_review|failed|skipped",
    )
    quality_report_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="M13 质检报告 ID")

    def __repr__(self) -> str:
        return f"<ImageGenerationTask id={self.id!r} type={self.asset_type!r} status={self.status!r}>"
