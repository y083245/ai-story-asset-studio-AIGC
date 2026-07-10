from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.config import settings
from app.modules.workflow.fake_activities import create_default_fake_activities
from app.modules.workflow.runner import FakeWorkflowRunner
from app.modules.workflow.schemas import WorkflowContext
from app.modules.workflow.workflows.full_generation import ProjectFullGenerationWorkflow


def _long_prompt(label: str) -> str:
    return (
        f"{label} final prompt with precise visual identity, consistent face, stable outfit, "
        "clear silhouette, reusable production asset, cinematic but readable lighting, "
        "clean composition, story-specific color palette, no random extra elements, "
        "high fidelity details for downstream visual asset generation. "
        "中文补充：保持角色、场景、道具锚点稳定，画面可复用，适合资产图生产。"
    )


def _negative_prompt() -> str:
    return (
        "low quality, blurry, watermark, logo, extra text, distorted hands, bad anatomy, "
        "inconsistent face, inconsistent outfit, missing prop, cluttered composition, random background"
    )


def _activities_with_generation_and_quality(quality_results: list[dict[str, Any]]) -> dict[str, Any]:
    activities = create_default_fake_activities()

    async def generate_character_image(**params: Any) -> dict[str, Any]:
        attempt = int(params.get("retry_attempt") or 0)
        return {
            "image_id": str(uuid.uuid4()),
            "generation_task_id": str(uuid.uuid4()),
            "type": "character",
            "prompt": _long_prompt("character"),
            "negative_prompt": _negative_prompt(),
            "retry_attempt": attempt,
            "url": "https://example.local/character.png",
        }

    async def generate_scene_image(**params: Any) -> dict[str, Any]:
        return {
            "image_id": str(uuid.uuid4()),
            "generation_task_id": str(uuid.uuid4()),
            "type": "scene",
            "prompt": _long_prompt("scene"),
            "negative_prompt": _negative_prompt(),
            "url": "https://example.local/scene.png",
        }

    async def generate_prop_image(**params: Any) -> dict[str, Any]:
        return {
            "image_id": str(uuid.uuid4()),
            "generation_task_id": str(uuid.uuid4()),
            "type": "prop",
            "prompt": _long_prompt("prop"),
            "negative_prompt": _negative_prompt(),
            "url": "https://example.local/prop.png",
        }

    async def check_image_quality(**params: Any) -> dict[str, Any]:
        if quality_results:
            return quality_results.pop(0)
        return {"passed": True, "score": 0.93, "issues": []}

    activities["generate_character_image"] = generate_character_image
    activities["generate_scene_image"] = generate_scene_image
    activities["generate_prop_image"] = generate_prop_image
    activities["check_image_quality"] = check_image_quality
    return activities


@pytest.mark.asyncio
async def test_full_asset_workflow_fake_provider_quality_retry_then_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vision_quality_enabled", True)
    monkeypatch.setattr(settings, "vision_quality_max_retries", 3)
    runner = FakeWorkflowRunner(
        _activities_with_generation_and_quality(
            [
                {"passed": False, "score": 0.42, "retry_prompt_patch": "keep identity stable", "issues": []},
                {"passed": True, "score": 0.91, "issues": []},
            ]
        )
    )

    result = await ProjectFullGenerationWorkflow().execute(
        runner,
        WorkflowContext(project_id="project-e2e", novel_text="第一章，她握着旧怀表走进冷白灯下的办公室。"),
    )

    assert result["characters"]
    assert result["scenes"]
    assert result["props"]
    all_assets = [*result["character_assets"], *result["scene_assets"], *result["prop_assets"]]
    assert len(all_assets) == 4
    assert all(asset["quality_status"] == "passed" for asset in all_assets)
    assert any(asset["retry_count"] == 1 for asset in all_assets)
    assert all(len(asset["prompt"]) > 200 for asset in all_assets)
    assert all(len(asset["negative_prompt"]) > 80 for asset in all_assets)
    assert len(result["image_quality_reports"]) == 5


@pytest.mark.asyncio
async def test_full_asset_workflow_vision_quality_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vision_quality_enabled", False)
    runner = FakeWorkflowRunner(_activities_with_generation_and_quality([]))

    result = await ProjectFullGenerationWorkflow().execute(
        runner,
        WorkflowContext(project_id="project-e2e-disabled", novel_text="第一章，测试文本。"),
    )

    all_assets = [*result["character_assets"], *result["scene_assets"], *result["prop_assets"]]
    assert len(all_assets) == 4
    assert all(asset["quality_status"] == "skipped" for asset in all_assets)
    assert result["image_quality_reports"] == []
