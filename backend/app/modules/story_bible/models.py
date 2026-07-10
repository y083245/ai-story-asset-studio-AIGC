"""Story Bible models for the visual asset pipeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class StoryBible(Base, UUIDMixin, TimestampMixin):
    """Current story reference data for one project."""

    __tablename__ = "story_bibles"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    genre: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    visual_style: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False, default="9:16")

    story_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    main_conflict: Mapped[str] = mapped_column(Text, nullable=False, default="")
    emotional_tone: Mapped[str] = mapped_column(Text, nullable=False, default="")
    world_setting: Mapped[str] = mapped_column(Text, nullable=False, default="")
    time_period: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    color_palette: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    composition_language: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    characters: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    scenes: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    props: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    negative_prompt_rules: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)

    def __repr__(self) -> str:
        return f"<StoryBible project_id={self.project_id!s} v{self.version}>"


class StoryBibleVersion(Base, UUIDMixin):
    """Immutable story bible snapshot."""

    __tablename__ = "story_bible_versions"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StoryBibleVersion project_id={self.project_id!s} v{self.version}>"
