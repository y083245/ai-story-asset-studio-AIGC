from __future__ import annotations

from typing import Any

import pytest

from app.config import settings
from app.modules.workflow.schemas import WorkflowContext
from app.modules.workflow.workflows.asset_generation import AssetGenerationWorkflow


class _QualityLoopRunner:
    def __init__(self, quality_results: list[dict[str, Any]]) -> None:
        self.quality_results = list(quality_results)
        self.generate_calls: list[dict[str, Any]] = []
        self.quality_calls: list[dict[str, Any]] = []
        self.auto_fix_calls: list[dict[str, Any]] = []
        self.progress: list[tuple[str, float]] = []

    async def update_progress(self, stage: str, progress: float, message: str | None = None) -> None:
        self.progress.append((stage, progress))

    async def run_activity(
        self,
        activity_name: str,
        context: WorkflowContext,
        params: dict[str, Any] | None = None,
        retry_policy: Any = None,
    ) -> dict[str, Any]:
        params = params or {}
        if activity_name == "generate_character_image":
            self.generate_calls.append(params)
            return {
                "image_id": f"asset-{len(self.generate_calls)}",
                "generation_task_id": f"task-{len(self.generate_calls)}",
                "type": "character",
                "url": f"https://example.local/{len(self.generate_calls)}.png",
                "prompt": f"prompt {len(self.generate_calls)}",
                "negative_prompt": "avoid blur",
            }
        if activity_name == "check_image_quality":
            self.quality_calls.append(params)
            return self.quality_results.pop(0)
        if activity_name == "auto_fix_image":
            self.auto_fix_calls.append(params)
            return {"fixed": True}
        raise AssertionError(f"unexpected activity {activity_name}")


def _context() -> WorkflowContext:
    return WorkflowContext(
        project_id="project-1",
        selected_style="urban",
        characters=[{"character_id": "CH_001", "name": "林晓"}],
        scenes=[],
        props=[],
        story_bible={"title": "旧怀表", "style_keywords": ["cinematic"]},
    )


@pytest.mark.asyncio
async def test_asset_generation_retries_failed_image_quality_then_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vision_quality_enabled", True)
    monkeypatch.setattr(settings, "vision_quality_max_retries", 3)
    runner = _QualityLoopRunner(
        [
            {"passed": False, "score": 0.42, "retry_prompt_patch": "make the face consistent", "issues": []},
            {"passed": True, "score": 0.91, "issues": []},
        ]
    )

    result = await AssetGenerationWorkflow().execute(runner, _context())

    assert len(runner.generate_calls) == 2
    assert len(runner.quality_calls) == 2
    assert runner.auto_fix_calls == []
    assert runner.generate_calls[1]["retry_attempt"] == 1
    assert runner.generate_calls[1]["retry_prompt_patch"] == "make the face consistent"
    asset = result["character_assets"][0]
    assert asset["quality_status"] == "passed"
    assert asset["retry_count"] == 1
    assert result["image_quality_reports"][-1]["passed"] is True


@pytest.mark.asyncio
async def test_asset_generation_marks_manual_review_after_retry_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vision_quality_enabled", True)
    monkeypatch.setattr(settings, "vision_quality_max_retries", 2)
    runner = _QualityLoopRunner(
        [
            {"passed": False, "score": 0.35, "retry_prompt_patch": "retry one", "issues": []},
            {"passed": False, "score": 0.40, "retry_prompt_patch": "retry two", "issues": []},
            {"passed": False, "score": 0.44, "retry_prompt_patch": "retry three", "issues": []},
        ]
    )

    result = await AssetGenerationWorkflow().execute(runner, _context())

    assert len(runner.generate_calls) == 3
    assert len(runner.quality_calls) == 3
    asset = result["character_assets"][0]
    assert asset["quality_status"] == "needs_manual_review"
    assert asset["retry_count"] == 2
    assert result["image_quality_reports"][-1]["needs_review"] is True


@pytest.mark.asyncio
async def test_asset_generation_skips_quality_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "vision_quality_enabled", False)
    runner = _QualityLoopRunner([])

    result = await AssetGenerationWorkflow().execute(runner, _context())

    assert len(runner.generate_calls) == 1
    assert runner.quality_calls == []
    asset = result["character_assets"][0]
    assert asset["quality_status"] == "skipped"
    assert result["image_quality_reports"] == []
