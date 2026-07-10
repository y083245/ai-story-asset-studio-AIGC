from __future__ import annotations

from typing import Any

import pytest

from app.modules.workflow.schemas import WorkflowContext
from app.modules.workflow.workflows.analyze import ProjectAnalyzeWorkflow


class _RecordingRunner:
    def __init__(self) -> None:
        self.progress: list[tuple[str, float, str | None]] = []

    async def update_progress(self, stage: str, progress: float, message: str | None = None) -> None:
        self.progress.append((stage, progress, message))

    async def run_activity(self, activity_name: str, _context: WorkflowContext, _params: dict[str, Any]) -> dict[str, Any]:
        results: dict[str, dict[str, Any]] = {
            "parse_novel": {"novel_id": "novel-1"},
            "clean_text": {"cleaned_text": "clean story", "chunks": [{"content": "clean story"}]},
            "detect_genre": {"confidence": 0.9, "style_id": "cinematic_realistic"},
            "extract_characters": {"characters": [{"name": "角色"}]},
            "extract_scenes": {"scenes": [{"name": "场景"}]},
            "extract_props": {"props": [{"name": "道具"}]},
            "build_story_bible": {"story_summary": "summary"},
        }
        return results[activity_name]


@pytest.mark.asyncio
async def test_analyze_workflow_waits_for_publication_before_completed_stage():
    runner = _RecordingRunner()
    workflow = ProjectAnalyzeWorkflow()

    await workflow.execute(runner, WorkflowContext(project_id="project-1", novel_text="raw story"))

    assert runner.progress[-1][0] == "publishing_analysis"
    assert runner.progress[-1][1] < 1.0
    assert all(stage != "completed" for stage, _progress, _message in runner.progress)
