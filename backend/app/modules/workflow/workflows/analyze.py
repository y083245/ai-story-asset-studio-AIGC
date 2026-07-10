"""Project analysis workflow for visual asset extraction."""

from __future__ import annotations

import asyncio
from typing import Any

from app.modules.workflow.progress import build_progress_message
from app.modules.workflow.schemas import WorkflowContext


class ProjectAnalyzeWorkflow:
    STAGE_PARSE = "parsing_novel"
    STAGE_GENRE = "detecting_genre"
    STAGE_WAIT_STYLE = "waiting_style_confirmation"
    STAGE_CHARACTERS = "extracting_characters"
    STAGE_SCENES = "extracting_scenes"
    STAGE_PROPS = "extracting_props"
    STAGE_BIBLE = "building_story_bible"
    STAGE_PUBLISH = "publishing_analysis"

    async def execute(self, runner: Any, context: WorkflowContext) -> dict[str, Any]:
        await runner.update_progress(self.STAGE_PARSE, 0.0)
        parsed = await runner.run_activity(
            "parse_novel", context, {"project_id": context.project_id, "text": context.novel_text}
        )
        context.parsed_data = parsed
        context.novel_id = str(parsed.get("novel_id", ""))
        await runner.update_progress(self.STAGE_PARSE, 0.08)

        await runner.update_progress("cleaning_text", 0.10)
        clean_result = await runner.run_activity(
            "clean_text", context, {"project_id": context.project_id, "novel_id": context.novel_id}
        )
        context.clean_text = str(clean_result.get("cleaned_text") or "")
        context.chunks = clean_result.get("chunks", [])
        await runner.update_progress("cleaning_text", 0.18)

        await runner.update_progress(self.STAGE_GENRE, 0.20)
        genre_result = await runner.run_activity(
            "detect_genre", context, {"project_id": context.project_id, "chunks": context.chunks}
        )
        context.genre_result = genre_result
        await runner.update_progress(self.STAGE_GENRE, 0.30)

        if genre_result.get("confidence", 0) < 0.75 and context.await_style_confirmation:
            await runner.update_progress(self.STAGE_WAIT_STYLE, 0.32)
            signal = await runner.wait_for_signal("style_confirmation", timeout=3600)
            context.style_confirmation_received = True
            context.selected_style = signal.get("selected_style", "")
            await runner.update_progress(self.STAGE_WAIT_STYLE, 0.36)

        selected_style_id = (
            context.selected_style
            or context.manual_style
            or str(genre_result.get("style_id") or genre_result.get("genre") or "")
        )
        context.selected_style = selected_style_id
        context.genre_result = {**context.genre_result, "style_id": selected_style_id}

        story_for_extraction = {"clean_text": context.clean_text, "parsed_data": context.parsed_data}
        await runner.update_progress(self.STAGE_CHARACTERS, 0.40)
        await runner.update_progress(self.STAGE_SCENES, 0.46)
        await runner.update_progress(self.STAGE_PROPS, 0.52)
        chars_result, scenes_result, props_result = await asyncio.gather(
            runner.run_activity(
                "extract_characters",
                context,
                {"project_id": context.project_id, "story": story_for_extraction, "style_id": selected_style_id},
            ),
            runner.run_activity(
                "extract_scenes",
                context,
                {"project_id": context.project_id, "story": story_for_extraction, "style_id": selected_style_id},
            ),
            runner.run_activity(
                "extract_props",
                context,
                {"project_id": context.project_id, "story": story_for_extraction, "style_id": selected_style_id},
            ),
        )
        context.characters = chars_result.get("characters", [])
        context.scenes = scenes_result.get("scenes", [])
        context.props = props_result.get("props", [])
        await runner.update_progress(self.STAGE_CHARACTERS, 0.58, f"角色提取完成：{len(context.characters)}个")
        await runner.update_progress(self.STAGE_SCENES, 0.66, f"场景提取完成：{len(context.scenes)}个")
        await runner.update_progress(self.STAGE_PROPS, 0.74, f"道具提取完成：{len(context.props)}个")

        await runner.update_progress(self.STAGE_BIBLE, 0.80)
        context.story_bible = await runner.run_activity(
            "build_story_bible",
            context,
            {
                "project_id": context.project_id,
                "characters": context.characters,
                "scenes": context.scenes,
                "props": context.props,
                "story": story_for_extraction,
                "style_id": selected_style_id,
            },
        )
        await runner.update_progress(self.STAGE_PUBLISH, 0.92, build_progress_message(self.STAGE_PUBLISH))
        return context.model_dump()

    @classmethod
    def name(cls) -> str:
        return "analyze"
