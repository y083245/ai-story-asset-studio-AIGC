"""SQLAlchemy ORM model for WorkflowState — tracks workflow execution progress.

This module owns the `workflow_states` table. All other modules have read-only access.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class WorkflowState(Base, UUIDMixin, TimestampMixin):
    """Tracks the current state of a project's workflow execution.

    One row per project — updated in-place by the workflow runner as stages complete,
    so the frontend can poll for progress.
    """

    __tablename__ = "workflow_states"

    # ---- Ownership ----
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )

    # ---- Which workflow is running ----
    workflow_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="analyze|asset|full",
    )

    # ---- Current position in the pipeline ----
    current_stage: Mapped[str] = mapped_column(
        String(100),
        default="idle",
        comment="e.g. parsing_novel, extracting_characters, generating_character_assets",
    )

    # ---- Progress (0.0 to 1.0) ----
    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    # ---- Human-readable status message (Chinese) ----
    message: Mapped[str] = mapped_column(
        String(500),
        default="",
    )

    # ---- Lifecycle status ----
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="pending|running|completed|failed|cancelled",
    )

    # ---- Per-activity task statuses (JSONB) ----
    # Maps activity_name -> {"status": "pending|running|success|failed", "result": ..., "attempt": int}
    task_states: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
    )

    # ---- Error tracking (nullable — only set on failure) ----
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True, default=None)
    error_stage: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)

    # ---- Signal handling (for style_confirmation and similar) ----
    awaiting_signal: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default=None,
        comment="e.g. style_confirmation",
    )
    signal_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)

    def __repr__(self) -> str:
        return (
            f"<WorkflowState project_id={self.project_id!s} "
            f"workflow_type={self.workflow_type!r} "
            f"stage={self.current_stage!r} progress={self.progress:.0%}>"
        )

    def record_activity_start(self, activity_name: str) -> None:
        """Mark an activity as running and initialise its task state if absent."""
        if self.task_states is None:
            self.task_states = {}
        if activity_name not in self.task_states:
            self.task_states[activity_name] = {}
        entry = self.task_states[activity_name]
        entry["status"] = "running"
        entry["attempt"] = entry.get("attempt", 0) + 1

    def record_activity_success(self, activity_name: str, result: dict[str, Any]) -> None:
        """Mark an activity as successful and store its result."""
        if self.task_states is None:
            self.task_states = {}
        if activity_name not in self.task_states:
            self.task_states[activity_name] = {}
        self.task_states[activity_name]["status"] = "success"
        self.task_states[activity_name]["result"] = result

    def record_activity_failure(self, activity_name: str, error: str) -> None:
        """Mark an activity as failed."""
        if self.task_states is None:
            self.task_states = {}
        if activity_name not in self.task_states:
            self.task_states[activity_name] = {}
        self.task_states[activity_name]["status"] = "failed"
        self.task_states[activity_name]["error"] = error

    def get_activity_result(self, activity_name: str) -> dict[str, Any] | None:
        """Return the saved result of a previously successful activity, or None."""
        if self.task_states is None:
            return None
        entry = self.task_states.get(activity_name, {})
        if entry.get("status") == "success":
            result: dict[str, Any] | None = entry.get("result")
            return result
        return None


class AnalysisStageChunk(Base, UUIDMixin, TimestampMixin):
    """Persist one successful or failed DeepSeek stage chunk for resume."""

    __tablename__ = "analysis_stage_chunks"
    __table_args__ = (
        Index(
            "ix_analysis_stage_chunks_cache_key",
            "project_id",
            "style_id",
            "module_id",
            "chunk_hash",
            unique=True,
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    style_id: Mapped[str] = mapped_column(String(80), nullable=False)
    module_id: Mapped[str] = mapped_column(String(120), nullable=False)
    model_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="default")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    result_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
