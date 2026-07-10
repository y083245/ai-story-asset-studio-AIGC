"""Build story reference data from project libraries."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.character_library.models import Character
from app.modules.project.models import Project
from app.modules.prop_library.models import Prop
from app.modules.scene_library.models import Scene
from app.modules.story_bible.validator import ReferenceValidator


class BibleAggregator:
    """Build a Story Bible from project, character, scene, and prop data."""

    @staticmethod
    async def build(
        session: AsyncSession,
        project_id: uuid.UUID,
        analysis_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = await BibleAggregator._get_project(session, project_id)
        analysis = analysis_output or {}
        characters = await BibleAggregator._get_characters(session, project_id)
        scenes = await BibleAggregator._get_scenes(session, project_id)
        props = await BibleAggregator._get_props(session, project_id)

        char_refs = [{"character_id": c.character_id, "name": c.name, "role": c.role_type} for c in characters]
        scene_refs = [{"scene_id": s.scene_id, "scene_name": s.scene_name, "type": s.scene_type} for s in scenes]
        prop_refs = [{"prop_id": p.prop_id, "name": p.name, "importance": p.importance} for p in props]

        validation_errors = await ReferenceValidator.validate(session, project_id, char_refs, scene_refs, prop_refs)
        if validation_errors:
            details = "; ".join(f"{item.entity_type}: {', '.join(item.missing_ids)}" for item in validation_errors)
            raise ValueError(f"Reference validation failed for project {project_id}: {details}")

        return {
            "project_id": str(project_id),
            "title": project.title,
            "genre": _text(analysis.get("genre")),
            "visual_style": _text(analysis.get("visual_style")),
            "aspect_ratio": str(project.aspect_ratio or "9:16"),
            "story_summary": _text(analysis.get("story_summary")),
            "main_conflict": _text(analysis.get("main_conflict")),
            "emotional_tone": _text(analysis.get("emotional_tone")),
            "world_setting": _text(analysis.get("world_setting")),
            "time_period": _text(analysis.get("time_period")),
            "color_palette": _string_list(analysis.get("color_palette")),
            "composition_language": _string_list(analysis.get("composition_language")),
            "characters": char_refs,
            "scenes": scene_refs,
            "props": prop_refs,
            "negative_prompt_rules": [
                {"rule": "文字，水印，logo，低质量，模糊，变形", "applies_to": "image"}
            ],
        }

    @staticmethod
    async def _get_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        return project

    @staticmethod
    async def _get_characters(session: AsyncSession, project_id: uuid.UUID) -> list[Character]:
        result = await session.execute(
            select(Character).where(Character.project_id == project_id).order_by(Character.sort_order)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _get_scenes(session: AsyncSession, project_id: uuid.UUID) -> list[Scene]:
        result = await session.execute(
            select(Scene).where(Scene.project_id == project_id).order_by(Scene.sort_order)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _get_props(session: AsyncSession, project_id: uuid.UUID) -> list[Prop]:
        result = await session.execute(select(Prop).where(Prop.project_id == project_id).order_by(Prop.prop_id))
        return list(result.scalars().all())


def _text(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []
