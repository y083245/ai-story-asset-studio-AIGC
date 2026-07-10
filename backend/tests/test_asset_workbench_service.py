from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.asset_workbench.schemas import (
    GenerateAssetWorkbenchRequest,
    GeneratedAssetItem,
    PreviewAssetWorkbenchPromptsRequest,
    PromptOverride,
)
from app.modules.asset_workbench.service import AssetWorkbenchService


class _FakeSession:
    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_workbench_prompt_overrides_do_not_become_generation_constraints(monkeypatch):
    project_id = uuid.uuid4()
    character = SimpleNamespace(character_id="CH_001", reference_assets=[])
    scene = SimpleNamespace(scene_id="SC_001", reference_assets=[])
    prop = SimpleNamespace(prop_id="PR_001", reference_assets=[])
    calls: list[dict[str, Any]] = []

    async def load_characters(_session: object, _project_id: uuid.UUID) -> list[SimpleNamespace]:
        return [character]

    async def load_scenes(_session: object, _project_id: uuid.UUID) -> list[SimpleNamespace]:
        return [scene]

    async def load_props(_session: object, _project_id: uuid.UUID) -> list[SimpleNamespace]:
        return [prop]

    async def generate_one(**kwargs: Any) -> GeneratedAssetItem:
        calls.append(kwargs)
        return GeneratedAssetItem(
            entity_type=kwargs["entity_type"],
            entity_id=kwargs["entity_id"],
            asset_type=kwargs["asset_type"],
            status="generated",
            storage_path=f"/tmp/{kwargs['asset_type']}.png",
        )

    monkeypatch.setattr(AssetWorkbenchService, "_load_characters", staticmethod(load_characters))
    monkeypatch.setattr(AssetWorkbenchService, "_load_scenes", staticmethod(load_scenes))
    monkeypatch.setattr(AssetWorkbenchService, "_load_props", staticmethod(load_props))

    service = AssetWorkbenchService(image_asset_service=object())  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_generate_one", generate_one)

    await service.generate_reference_assets(
        session=_FakeSession(),  # type: ignore[arg-type]
        project_id=project_id,
        request=GenerateAssetWorkbenchRequest(
            targets=["characters", "scenes", "props"],
            prompt_overrides=[
                PromptOverride(entity_type="character", entity_id="CH_001", prompt="full character prompt"),
                PromptOverride(entity_type="scene", entity_id="SC_001", prompt="full scene prompt"),
                PromptOverride(entity_type="prop", entity_id="PR_001", prompt="full prop prompt"),
            ],
        ),
    )

    assert [call["asset_type"] for call in calls] == [
        "character_front",
        "character_turnaround",
        "scene_empty",
        "prop_product",
    ]
    assert all(call.get("extra_constraints") is None for call in calls)


@pytest.mark.asyncio
async def test_workbench_previews_final_prompts_for_all_asset_types():
    project_id = uuid.uuid4()
    calls: list[dict[str, Any]] = []

    class FakeImageAssetService:
        async def build_prompt_preview(self, request: Any, _session: Any) -> Any:
            calls.append(
                {
                    "project_id": request.project_id,
                    "asset_type": request.asset_type,
                    "related_id": request.related_id,
                    "reference_asset_ids": request.reference_asset_ids,
                }
            )
            return SimpleNamespace(
                prompt=f"final prompt for {request.asset_type}",
                negative_prompt=f"negative prompt for {request.asset_type}",
            )

    service = AssetWorkbenchService(image_asset_service=FakeImageAssetService())  # type: ignore[arg-type]

    response = await service.preview_prompts(
        session=_FakeSession(),  # type: ignore[arg-type]
        project_id=project_id,
        request=PreviewAssetWorkbenchPromptsRequest(
            items=[
                {"entity_type": "character", "entity_id": "CH_001", "asset_type": "character_front"},
                {
                    "entity_type": "character",
                    "entity_id": "CH_001",
                    "asset_type": "character_turnaround",
                    "reference_asset_ids": ["projects/p1/characters/CH_001/front.png"],
                },
                {"entity_type": "scene", "entity_id": "SC_001", "asset_type": "scene_empty"},
                {"entity_type": "prop", "entity_id": "PR_001", "asset_type": "prop_product"},
            ]
        ),
    )

    assert [call["asset_type"] for call in calls] == [
        "character_front",
        "character_turnaround",
        "scene_empty",
        "prop_product",
    ]
    assert calls[1]["reference_asset_ids"] == ["projects/p1/characters/CH_001/front.png"]
    assert [item.prompt for item in response.items] == [
        "final prompt for character_front",
        "final prompt for character_turnaround",
        "final prompt for scene_empty",
        "final prompt for prop_product",
    ]
    assert [item.negative_prompt for item in response.items] == [
        "negative prompt for character_front",
        "negative prompt for character_turnaround",
        "negative prompt for scene_empty",
        "negative prompt for prop_product",
    ]
