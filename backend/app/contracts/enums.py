"""Project-level enumerations shared across Story Asset Studio modules.

These enums define the canonical value sets for project status, task status,
style mode, generation mode, and aspect ratio. All modules MUST use these
enums rather than raw string literals.
"""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    """Lifecycle status of a visual asset project."""

    DRAFT = "draft"
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    ANALYSIS_CONFIRMED = "analysis_confirmed"
    GENERATING_ASSETS = "generating_assets"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    """Lifecycle status of an individual generation / processing task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class StyleMode(StrEnum):
    """How the visual style for a project is determined."""

    AUTO = "auto"
    MANUAL = "manual"


class GenerationMode(StrEnum):
    """Generation quality / speed trade-off mode."""

    FAST_PREVIEW = "fast_preview"
    HIGH_QUALITY = "high_quality"


class AspectRatio(StrEnum):
    """Supported output aspect ratios."""

    RATIO_9_16 = "9:16"
    RATIO_16_9 = "16:9"
