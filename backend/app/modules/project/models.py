"""SQLAlchemy ORM models for the Project module.

Exclusive write ownership:
- projects
- project_settings
- project_status_snapshots

Read-only references (do NOT write):
- workflow_runs (Workflow)
- quality_reports
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.contracts.enums import GenerationMode, ProjectStatus, StyleMode
from app.db.base import Base, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin):
    """Project master table — one row per visual asset project."""

    __tablename__ = "projects"

    # ---- Ownership & Identity ----
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # ---- Lifecycle ----
    status: Mapped[ProjectStatus] = mapped_column(
        String(50),
        nullable=False,
        default=ProjectStatus.DRAFT,
        index=True,
    )

    # ---- Asset Generation Parameters (locked during active generation) ----
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False, default="9:16")
    style_mode: Mapped[StyleMode] = mapped_column(String(20), nullable=False, default=StyleMode.AUTO)
    manual_style: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    generation_mode: Mapped[GenerationMode] = mapped_column(
        String(20), nullable=False, default=GenerationMode.FAST_PREVIEW
    )

    # ---- Progress (JSON blob for flexible UI needs) ----
    progress_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # ---- Recycle bin ----
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # ---- Relationships ----
    settings: Mapped[list[ProjectSettings]] = relationship(
        "ProjectSettings", back_populates="project", cascade="all, delete-orphan"
    )
    status_snapshots: Mapped[list[ProjectStatusSnapshot]] = relationship(
        "ProjectStatusSnapshot", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id!s} title={self.title!r} status={self.status!r}>"


class ProjectSettings(Base, UUIDMixin, TimestampMixin):
    """Fine-grained per-project settings keyed by project_id."""

    __tablename__ = "project_settings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # ---- Relationships ----
    project: Mapped[Project] = relationship("Project", back_populates="settings")

    def __repr__(self) -> str:
        return f"<ProjectSettings project_id={self.project_id!s} key={self.key!r}>"


class ProjectStatusSnapshot(Base, UUIDMixin):
    """Point-in-time status snapshot for historical tracking."""

    __tablename__ = "project_status_snapshots"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # ---- Relationships ----
    project: Mapped[Project] = relationship("Project", back_populates="status_snapshots")

    def __repr__(self) -> str:
        return f"<ProjectStatusSnapshot project_id={self.project_id!s} stage={self.stage!r}>"
