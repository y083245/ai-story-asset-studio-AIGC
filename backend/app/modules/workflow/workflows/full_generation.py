"""One-click analysis plus image asset generation workflow."""

from __future__ import annotations

from typing import Any

from app.modules.workflow.progress import build_progress_message
from app.modules.workflow.schemas import WorkflowContext
from app.modules.workflow.workflows.analyze import ProjectAnalyzeWorkflow
from app.modules.workflow.workflows.asset_generation import AssetGenerationWorkflow


class ProjectFullGenerationWorkflow:
    STAGE_ANALYZE = "full_generation_analyze"
    STAGE_ASSET = "full_generation_asset"

    async def execute(self, runner: Any, context: WorkflowContext) -> dict[str, Any]:
        await runner.update_progress(self.STAGE_ANALYZE, 0.05, build_progress_message(self.STAGE_ANALYZE))
        context = await runner.execute_sub_workflow(ProjectAnalyzeWorkflow(), context)
        await runner.update_progress(self.STAGE_ASSET, 0.55, build_progress_message(self.STAGE_ASSET))
        context = await runner.execute_sub_workflow(AssetGenerationWorkflow(), context)
        await runner.update_progress("completed", 1.0, build_progress_message("completed"))
        return context.model_dump()

    @classmethod
    def name(cls) -> str:
        return "full"
