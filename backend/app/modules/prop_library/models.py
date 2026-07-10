"""SQLAlchemy ORM models for the Prop Library module.

Exclusive write ownership:
- props
- prop_versions
- generation_tasks (task_type = "prop_regenerate")

Read-only references:
- prop reference assets from M11 (not tracked here)

Design notes:
- Every user edit on a prop creates a PropVersion row before
  the Prop row is mutated.
- prop_id is a stable human-readable string (PR_001, PR_002, ...)
  assigned by the M00 ID factory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.contracts.enums import TaskStatus
from app.db.base import Base, TimestampMixin, UUIDMixin


class Prop(Base, UUIDMixin, TimestampMixin):
    """Prop master table — one row per story prop."""

    __tablename__ = "props"
    __table_args__ = (Index("ix_props_project_prop_id", "project_id", "prop_id", unique=True),)

    # ---- Identity ----
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    prop_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="稳定道具 ID，如 PR_001")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="道具规范名称")
    aliases: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, comment="别名列表 (合并后的称呼/外号)")
    importance: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="minor", default="minor", comment="重要度: core|supporting|minor"
    )
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="道具类别: 武器/饰品/信物/衣物/器物等"
    )

    # ---- Ownership ----
    owner_character_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True, comment="所属角色 ID (CH_xxx)，可为空"
    )

    # ---- Physical description ----
    visual_features: Mapped[str | None] = mapped_column(Text, nullable=True, comment="视觉特征描述")
    material: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="材质")
    color: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="颜色")
    size: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="尺寸")

    # ---- Story context ----
    first_appearance: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="首次出场定位，如「第1幕：苏念手持合同站在大厦楼下」"
    )
    plot_function: Mapped[str | None] = mapped_column(Text, nullable=True, comment="剧情功能，道具在故事中的作用")

    # ---- State timeline ----
    state_timeline: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list, comment="状态时间线，记录道具在不同剧情节拍的状态变化"
    )

    # ---- AI-generated Prompts ----
    prop_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, comment="纯白背景单品图绘图提示词")
    usage_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="场景内摆放/手持/特写使用图绘图提示词"
    )

    # ---- Asset References ----
    canonical_asset_id: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Canonical reference asset storage_path/id"
    )
    reference_assets: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="已生成的参考图 asset_id 列表 (由 M11 回填)"
    )

    # ---- Relationships ----
    versions: Mapped[list[PropVersion]] = relationship(
        "PropVersion", back_populates="prop", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Prop prop_id={self.prop_id!r} name={self.name!r}>"


class PropVersion(Base, UUIDMixin):
    """Version history for a prop — created before every user edit."""

    __tablename__ = "prop_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "prop_id"],
            ["props.project_id", "props.prop_id"],
            ondelete="CASCADE",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    prop_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="所属道具 ID",
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
    prop: Mapped[Prop] = relationship("Prop", back_populates="versions")

    def __repr__(self) -> str:
        return f"<PropVersion prop_id={self.prop_id!r} v{self.version_number}>"


class GenerationTask(Base):
    """Lightweight generation task record for prop regeneration.

    This table tracks the status of a regenerate request so that the
    Workflow module can pick it up and dispatch the actual work to M11.
    """

    __tablename__ = "prop_generation_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True, comment="所属项目 ID")
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, default="prop_regenerate", comment="任务类型")
    target_id: Mapped[str] = mapped_column(String(50), nullable=False, comment="目标道具 ID (PR_001)")
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
