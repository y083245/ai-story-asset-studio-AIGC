"""SQLAlchemy ORM models for the Scene Library module.

Exclusive write ownership:
- scenes
- scene_versions
- generation_tasks (task_type = "scene_regenerate")

Read-only references:
- scene reference assets from M11 (not tracked here)

Design notes:
- Every user edit on a scene creates a SceneVersion row before
  the Scene row is mutated.
- scene_id is a stable human-readable string (SC_001, SC_002, ...)
  assigned by the M00 ID factory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKeyConstraint, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.contracts.enums import TaskStatus
from app.db.base import Base, TimestampMixin, UUIDMixin


class Scene(Base, UUIDMixin, TimestampMixin):
    """Scene master table — one row per story scene."""

    __tablename__ = "scenes"
    __table_args__ = (Index("ix_scenes_project_scene_id", "project_id", "scene_id", unique=True),)

    # ---- Identity ----
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    scene_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="稳定场景 ID，如 SC_001")
    scene_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="场景名称，至少4个中文字符")
    scene_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="室内", default="室内", comment="场景类型：室内/室外/混合"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0, comment="在项目内的排序序号"
    )

    # ---- Atmosphere ----
    time_of_day: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="时段：早晨/正午/黄昏/夜晚")
    weather: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="天气：晴天/阴天/雨天/雪天")
    lighting: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="光照描述")
    mood: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="场景氛围/情绪基调")
    color_palette: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, comment="色彩调色板")

    # ---- Spatial Composition ----
    fixed_anchors: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, comment="固定锚点列表，至少3个"
    )
    foreground_elements: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, comment="前景元素")
    midground_elements: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, comment="中景元素")
    background_elements: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, comment="背景元素")

    # ---- Composition & Restrictions ----
    composition_views: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, comment="允许的构图视角列表")
    forbidden_elements: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="禁止出现的元素（人物、文字、水印、logo等）"
    )

    # ---- AI-generated Prompts ----
    scene_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="场景描述prompt，不包含角色姓名")
    empty_scene_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment='空场景prompt，以"不能出现其他人，无人纯场景，"开头'
    )

    # ---- Quality ----
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="场景一致性分数 0.0-1.0")

    # ---- Asset References ----
    canonical_asset_id: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Canonical reference asset storage_path/id"
    )
    reference_assets: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="已生成的参考图 asset_id 列表 (由 M11 回填)"
    )

    # ---- Relationships ----
    versions: Mapped[list[SceneVersion]] = relationship(
        "SceneVersion", back_populates="scene", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Scene scene_id={self.scene_id!r} scene_name={self.scene_name!r}>"


class SceneVersion(Base, UUIDMixin):
    """Version history for a scene — created before every user edit."""

    __tablename__ = "scene_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "scene_id"],
            ["scenes.project_id", "scenes.scene_id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    scene_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="所属场景 ID",
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号 (从1递增)")
    changed_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, comment="本次修改的字段列表")
    previous_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, comment="修改前的字段值快照")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # ---- Relationships ----
    scene: Mapped[Scene] = relationship("Scene", back_populates="versions")

    def __repr__(self) -> str:
        return f"<SceneVersion scene_id={self.scene_id!r} v{self.version_number}>"


class GenerationTask(Base):
    """Lightweight generation task record for scene regeneration.

    This table tracks the status of a regenerate request so that the
    Workflow module can pick it up and dispatch the actual work to M11.
    """

    __tablename__ = "scene_generation_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, default="scene_regenerate", comment="任务类型")
    target_id: Mapped[str] = mapped_column(String(50), nullable=False, comment="目标场景 ID (SC_001)")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.PENDING, comment="任务状态")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, comment="任务 payload")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, comment="任务结果")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<GenerationTask type={self.task_type!r} target={self.target_id!r} status={self.status!r}>"
