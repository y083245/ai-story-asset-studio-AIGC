from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class AssetStage:
    stage_name: str
    asset_type: str
    reference_stages: list[str] = field(default_factory=list)
    timeout: int = 120
    priority: int = 0


@dataclass(frozen=True)
class AssetGenerationPlan:
    entity_id: str
    entity_type: str
    stages: list[AssetStage]


class AssetPipelinePlanner:
    def plan_character_pipeline(self, character: Any) -> AssetGenerationPlan:
        entity_id = self._read_entity_id(character, "character_id")
        return AssetGenerationPlan(
            entity_id=entity_id,
            entity_type="character",
            stages=[
                AssetStage(
                    stage_name="bible_sheet",
                    asset_type="character_bible_sheet",
                    timeout=settings.canonical_bible_sheet_timeout_seconds,
                    priority=0,
                ),
                AssetStage(
                    stage_name="front",
                    asset_type="character_front",
                    reference_stages=["bible_sheet"],
                    priority=1,
                ),
                AssetStage(
                    stage_name="turnaround",
                    asset_type="character_turnaround",
                    reference_stages=["bible_sheet"],
                    priority=1,
                ),
                AssetStage(
                    stage_name="expression",
                    asset_type="character_expression",
                    reference_stages=["bible_sheet"],
                    priority=1,
                ),
            ],
        )

    def plan_scene_pipeline(self, scene: Any) -> AssetGenerationPlan:
        entity_id = self._read_entity_id(scene, "scene_id")
        return AssetGenerationPlan(
            entity_id=entity_id,
            entity_type="scene",
            stages=[
                AssetStage(
                    stage_name="scene_empty",
                    asset_type="scene_empty",
                    priority=0,
                ),
                AssetStage(
                    stage_name="scene_with_atmosphere",
                    asset_type="scene_with_atmosphere",
                    reference_stages=["scene_empty"],
                    priority=1,
                ),
            ],
        )

    def plan_prop_pipeline(self, prop: Any) -> AssetGenerationPlan:
        entity_id = self._read_entity_id(prop, "prop_id")
        return AssetGenerationPlan(
            entity_id=entity_id,
            entity_type="prop",
            stages=[
                AssetStage(
                    stage_name="prop_product",
                    asset_type="prop_product",
                    priority=0,
                ),
                AssetStage(
                    stage_name="prop_usage",
                    asset_type="prop_usage",
                    reference_stages=["prop_product"],
                    priority=1,
                ),
            ],
        )

    @staticmethod
    def _read_entity_id(entity: Any, attribute_name: str) -> str:
        raw_entity_id = getattr(entity, attribute_name, None)
        if raw_entity_id is None:
            raise ValueError(f"Unknown or empty entity id: missing {attribute_name}")

        entity_id = str(raw_entity_id).strip()
        if not entity_id:
            raise ValueError(f"Unknown or empty entity id: {attribute_name}")
        return entity_id


__all__ = ["AssetGenerationPlan", "AssetPipelinePlanner", "AssetStage"]
