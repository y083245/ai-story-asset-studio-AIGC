"""Domain event contracts for Story Asset Studio.

Every significant state transition in the system emits a typed domain event.
These dataclasses define the canonical event shapes. All events carry:
- event_id:    unique identifier for this event occurrence
- project_id:  the project this event belongs to
- occurred_at: ISO-8601 timestamp string
- payload:     event-specific data (dict)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat()


class EventType(StrEnum):
    """Canonical domain event types."""

    PROJECT_CREATED = "project.created"
    NOVEL_UPLOADED = "novel.uploaded"
    ANALYSIS_COMPLETED = "analysis.completed"
    ASSET_GENERATED = "asset.generated"
    QUALITY_FAILED = "quality.failed"


@dataclass(frozen=True, slots=True)
class ProjectCreated:
    """Emitted when a new project is created."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    occurred_at: str = field(default_factory=_utc_now_iso)
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class NovelUploaded:
    """Emitted when a novel is successfully uploaded and preprocessed."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    occurred_at: str = field(default_factory=_utc_now_iso)
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AnalysisCompleted:
    """Emitted when the full story analysis (genre, bible, extraction) finishes."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    occurred_at: str = field(default_factory=_utc_now_iso)
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AssetGenerated:
    """Emitted when an image asset (character/scene/prop) is generated."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    occurred_at: str = field(default_factory=_utc_now_iso)
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
@dataclass(frozen=True, slots=True)
class QualityFailed:
    """Emitted when quality check fails for an image asset."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    occurred_at: str = field(default_factory=_utc_now_iso)
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
