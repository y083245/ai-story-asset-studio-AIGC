"""SQLAlchemy ORM models for the Quality & Retry module.

Exclusive write ownership:
- quality_reports
- retry_decisions

Read/write references (owned by other modules):
- image_generation_tasks.retry_count
- image_generation_tasks.quality_status
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class QualityReport(Base, UUIDMixin, TimestampMixin):
    """Quality inspection report for a generated asset."""

    __tablename__ = "quality_reports"

    # ---- Identity ----
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    related_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True, comment="关联实体 ID")
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, comment="引用 ImageAsset.id"
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="资产类型: image")
    generation_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, comment="关联的生成任务 ID"
    )

    # ---- Scores ----
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="综合质量评分 0.0-1.0")
    face_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="面部一致性评分")
    outfit_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="服装一致性评分")
    scene_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="场景一致性评分")
    prop_presence_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="道具存在性评分")
    composition_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="构图评分")

    # ---- Issues detected ----
    issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, comment="检测到的问题列表"
    )

    # ---- Decision ----
    retry_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否需要重试")
    retry_prompt_patch: Mapped[str | None] = mapped_column(Text, nullable=True, comment="重试用的 prompt 修补文本")
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否需要人工审核")
    report_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, comment="完整的质检报告 JSON"
    )

    def __repr__(self) -> str:
        return (
            f"<QualityReport id={self.id!r} related={self.related_id!r} "
            f"score={self.quality_score:.2f} retry={self.retry_required}>"
        )


class RetryDecision(Base, UUIDMixin, TimestampMixin):
    """Retry decision record tracking retry counts and outcomes."""

    __tablename__ = "retry_decisions"

    # ---- Identity ----
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    generation_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, comment="关联的生成任务 ID"
    )
    related_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True, comment="关联实体 ID")
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="资产类型: image")

    # ---- Retry counts ----
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="当前已重试次数")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, comment="最大重试次数")
    max_auto_fixes: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment="最大自动修复次数")
    auto_fix_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已自动修复次数")

    # ---- Decision ----
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="决策动作: retry | needs_review | passed",
    )
    retry_prompt_patch: Mapped[str | None] = mapped_column(Text, nullable=True, comment="重试 prompt 修补内容")
    previous_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="上一次生成使用的 prompt")
    quality_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="关联的 quality_reports.id"
    )

    # ---- Outcome ----
    outcome: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="执行结果: success | failed | pending"
    )

    def __repr__(self) -> str:
        return f"<RetryDecision id={self.id!r} action={self.action!r} retry={self.retry_count}/{self.max_retries}>"
