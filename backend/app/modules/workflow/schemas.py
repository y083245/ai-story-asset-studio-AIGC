"""Workflow API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowContext(BaseModel):
    """Mutable context passed through workflow steps."""

    project_id: str
    user_id: str = ""
    novel_text: str = ""
    novel_id: str = ""

    aspect_ratio: str = "9:16"
    style_mode: str = "auto"
    manual_style: str = ""
    generation_mode: str = "fast_preview"

    parsed_data: dict[str, Any] = Field(default_factory=dict)
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    clean_text: str = ""
    genre_result: dict[str, Any] = Field(default_factory=dict)
    characters: list[dict[str, Any]] = Field(default_factory=list)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    props: list[dict[str, Any]] = Field(default_factory=list)
    story_bible: dict[str, Any] = Field(default_factory=dict)

    character_assets: list[dict[str, Any]] = Field(default_factory=list)
    scene_assets: list[dict[str, Any]] = Field(default_factory=list)
    prop_assets: list[dict[str, Any]] = Field(default_factory=list)
    image_quality_reports: list[dict[str, Any]] = Field(default_factory=list)

    await_style_confirmation: bool = False
    style_confirmation_received: bool = False
    selected_style: str = ""

    model_config = {"extra": "allow"}


class WorkflowStartRequest(BaseModel):
    pass


class AnalyseRequest(WorkflowStartRequest):
    novel_text: str | None = None


class GenerateAssetsRequest(WorkflowStartRequest):
    pass


class GenerateRequest(WorkflowStartRequest):
    pass


class CancelRequest(WorkflowStartRequest):
    reason: str = "user_cancelled"


class SignalRequest(BaseModel):
    signal_name: str = Field(..., description="e.g. style_confirmation")
    data: dict[str, Any] = Field(default_factory=dict)


class ActivityState(BaseModel):
    activity_name: str
    status: str
    attempt: int = 0
    error: str | None = None
    result_summary: dict[str, Any] | None = None


class WorkflowStatusResponse(BaseModel):
    project_id: str
    workflow_type: str
    status: str
    current_stage: str
    progress: float
    message: str
    awaiting_signal: str | None = None
    error: str | None = None
    error_stage: str | None = None
    activities: list[ActivityState] = Field(default_factory=list)


class WorkflowStartedResponse(BaseModel):
    project_id: str
    workflow_type: str
    status: str = "running"
    message: str


class WorkflowCancelledResponse(BaseModel):
    project_id: str
    status: str = "cancelled"
    message: str


class SignalResponse(BaseModel):
    project_id: str
    signal_name: str
    received: bool = True
    message: str
