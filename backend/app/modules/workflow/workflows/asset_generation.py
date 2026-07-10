"""Image asset generation workflow."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.modules.workflow.progress import build_progress_message
from app.modules.workflow.retry_policy import IMAGE_RETRY_POLICY
from app.modules.workflow.schemas import WorkflowContext


class AssetGenerationWorkflow:
    STAGE_CHARACTER = "generating_character_assets"
    STAGE_SCENE = "generating_scene_assets"
    STAGE_PROP = "generating_prop_assets"
    STAGE_QUALITY = "checking_image_quality"
    STAGE_RETRY = "retrying_failed_images"

    async def execute(self, runner: Any, context: WorkflowContext) -> dict[str, Any]:
        style = context.selected_style or context.manual_style or context.style_mode or "auto"
        reports: list[dict[str, Any]] = []

        character_assets: list[dict[str, Any]] = []
        await runner.update_progress(self.STAGE_CHARACTER, 0.05)
        for index, character in enumerate(context.characters):
            result = await self._generate_with_quality_loop(
                runner=runner,
                context=context,
                activity_name="generate_character_image",
                generate_params={"project_id": context.project_id, "character": character, "style": style},
                reports=reports,
                error_fallback={"character_name": character.get("name", "")},
            )
            character_assets.append(result)
            await runner.update_progress(self.STAGE_CHARACTER, 0.05 + 0.25 * (index + 1) / max(1, len(context.characters)))
        context.character_assets = character_assets

        scene_assets: list[dict[str, Any]] = []
        await runner.update_progress(self.STAGE_SCENE, 0.35)
        for index, scene in enumerate(context.scenes):
            result = await self._generate_with_quality_loop(
                runner=runner,
                context=context,
                activity_name="generate_scene_image",
                generate_params={"project_id": context.project_id, "scene": scene, "style": style},
                reports=reports,
                error_fallback={"scene_name": scene.get("name", "")},
            )
            scene_assets.append(result)
            await runner.update_progress(self.STAGE_SCENE, 0.35 + 0.20 * (index + 1) / max(1, len(context.scenes)))
        context.scene_assets = scene_assets

        prop_assets: list[dict[str, Any]] = []
        await runner.update_progress(self.STAGE_PROP, 0.60)
        for index, prop in enumerate(context.props):
            result = await self._generate_with_quality_loop(
                runner=runner,
                context=context,
                activity_name="generate_prop_image",
                generate_params={"project_id": context.project_id, "prop": prop, "style": style},
                reports=reports,
                error_fallback={"prop_name": prop.get("name", "")},
            )
            prop_assets.append(result)
            await runner.update_progress(self.STAGE_PROP, 0.60 + 0.15 * (index + 1) / max(1, len(context.props)))
        context.prop_assets = prop_assets

        await runner.update_progress(self.STAGE_QUALITY, 0.82)
        context.image_quality_reports = reports

        await runner.update_progress(self.STAGE_RETRY, 0.92)

        await runner.update_progress("completed", 1.0, build_progress_message("completed"))
        return context.model_dump()

    @classmethod
    def name(cls) -> str:
        return "asset"

    async def _generate_with_quality_loop(
        self,
        *,
        runner: Any,
        context: WorkflowContext,
        activity_name: str,
        generate_params: dict[str, Any],
        reports: list[dict[str, Any]],
        error_fallback: dict[str, Any],
    ) -> dict[str, Any]:
        retry_history: list[dict[str, Any]] = []
        retry_attempt = 0
        max_retries = max(0, settings.vision_quality_max_retries)
        current_params = dict(generate_params)

        while True:
            try:
                asset = await runner.run_activity(
                    activity_name,
                    context,
                    current_params,
                    retry_policy=IMAGE_RETRY_POLICY,
                )
            except Exception as exc:
                return {
                    "error": str(exc),
                    "quality_status": "failed",
                    "retry_count": retry_attempt,
                    **error_fallback,
                }

            asset["retry_count"] = retry_attempt
            if retry_history:
                asset["retry_history"] = list(retry_history)

            if not settings.vision_quality_enabled:
                asset["quality_status"] = "skipped"
                return asset

            try:
                report = await runner.run_activity(
                    "check_image_quality",
                    context,
                    {
                        "project_id": context.project_id,
                        "images": asset,
                        "prompt": asset.get("prompt", ""),
                        "negative_prompt": asset.get("negative_prompt", ""),
                        "asset_bible": context.story_bible,
                        "style_keywords": _style_keywords(context),
                        "retry_history": retry_history,
                        "retry_count": retry_attempt,
                    },
                )
            except Exception as exc:
                report = {
                    "passed": False,
                    "needs_review": False,
                    "issues": [{"type": "check_error", "error": str(exc)}],
                    "retry_prompt_patch": "",
                }

            report.setdefault("asset_id", asset.get("asset_id") or asset.get("image_id"))
            report.setdefault("generation_task_id", asset.get("generation_task_id"))
            report["retry_count"] = retry_attempt
            reports.append(report)

            if report.get("passed", False):
                asset["quality_status"] = "passed"
                return asset

            if retry_attempt >= max_retries:
                report["needs_review"] = True
                asset["quality_status"] = "needs_manual_review"
                asset["retry_count"] = retry_attempt
                return asset

            retry_attempt += 1
            retry_prompt_patch = str(report.get("retry_prompt_patch") or report.get("prompt_patch") or "")
            retry_history.append(
                {
                    "attempt": retry_attempt,
                    "quality_report": report,
                    "prompt_patch": retry_prompt_patch,
                }
            )
            current_params = {
                **generate_params,
                "retry_attempt": retry_attempt,
                "retry_prompt_patch": retry_prompt_patch,
                "retry_history": retry_history,
            }


def _style_keywords(context: WorkflowContext) -> list[str]:
    story_bible = context.story_bible if isinstance(context.story_bible, dict) else {}
    raw_keywords = story_bible.get("style_keywords") or story_bible.get("visual_keywords") or []
    if not isinstance(raw_keywords, list):
        return []
    return [str(keyword) for keyword in raw_keywords if str(keyword).strip()]
