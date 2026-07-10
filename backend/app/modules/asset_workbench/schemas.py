"""Schemas for the merged asset workbench."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

AssetWorkbenchTarget = Literal["characters", "scenes", "props"]
AssetWorkbenchEntityType = Literal["character", "scene", "prop"]


def _default_targets() -> list[AssetWorkbenchTarget]:
    return ["characters", "scenes", "props"]


class PromptOverride(BaseModel):
    """Optional generation prompt constraint for a specific library entity."""

    entity_type: AssetWorkbenchEntityType
    entity_id: str = Field(..., min_length=1, max_length=20)
    prompt: str = Field(..., min_length=1, max_length=2000)

    model_config = {"extra": "forbid"}


class GenerateAssetWorkbenchRequest(BaseModel):
    """Request for one-click reference image generation."""

    targets: list[AssetWorkbenchTarget] = Field(
        default_factory=_default_targets,
        min_length=1,
        max_length=3,
    )
    prompt_overrides: list[PromptOverride] = Field(default_factory=list, max_length=200)
    only_missing: bool = False

    model_config = {"extra": "forbid"}


class PromptPreviewItem(BaseModel):
    """One asset prompt preview target."""

    entity_type: AssetWorkbenchEntityType
    entity_id: str = Field(..., min_length=1, max_length=20)
    asset_type: str = Field(
        ...,
        pattern=(
            r"^(character_bible_sheet|character_front|character_turnaround|character_expression|"
            r"scene_empty|scene_with_atmosphere|prop_product|prop_usage)$"
        ),
    )
    reference_asset_ids: list[str] = Field(default_factory=list)
    extra_constraints: str | None = Field(None, max_length=2000)

    model_config = {"extra": "forbid"}


class PreviewAssetWorkbenchPromptsRequest(BaseModel):
    """Request for final prompt previews without generating images."""

    items: list[PromptPreviewItem] = Field(..., min_length=1, max_length=200)

    model_config = {"extra": "forbid"}


class PromptPreviewResult(BaseModel):
    """One final prompt preview result."""

    entity_type: AssetWorkbenchEntityType
    entity_id: str
    asset_type: str
    prompt: str
    negative_prompt: str


class PreviewAssetWorkbenchPromptsResponse(BaseModel):
    """Response for final prompt previews."""

    items: list[PromptPreviewResult]


class GeneratedAssetItem(BaseModel):
    """One generated, skipped, or failed asset result."""

    entity_type: AssetWorkbenchEntityType
    entity_id: str
    asset_type: str
    status: Literal["generated", "skipped", "failed"]
    storage_path: str | None = None
    error: str | None = None


class GenerateAssetWorkbenchResponse(BaseModel):
    """Response from the merged asset generation endpoint."""

    project_id: uuid.UUID
    total: int
    succeeded: int
    skipped: int
    failed: int
    results: list[GeneratedAssetItem]
