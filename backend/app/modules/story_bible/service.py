"""Story Bible service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.story_bible.aggregator import BibleAggregator
from app.modules.story_bible.models import StoryBible, StoryBibleVersion
from app.modules.story_bible.schemas import StoryBiblePatchRequest


class StoryBibleService:
    """Stateless Story Bible management service."""

    @staticmethod
    async def build_bible(
        session: AsyncSession,
        project_id: uuid.UUID,
        analysis_output: dict[str, Any] | None = None,
    ) -> StoryBible:
        bible_data = await BibleAggregator.build(session, project_id, analysis_output)
        existing = await StoryBibleService._get_bible_by_project(session, project_id)
        if existing is None:
            bible = StoryBible(project_id=project_id, version=1)
            StoryBibleService._apply_data_to_bible(bible, {**bible_data, "version": 1})
            session.add(bible)
            session.add(StoryBibleVersion(project_id=project_id, version=1, snapshot=StoryBibleService._bible_to_dict(bible)))
            await session.flush()
            return bible

        new_version = existing.version + 1
        StoryBibleService._apply_data_to_bible(existing, {**bible_data, "version": new_version})
        session.add(
            StoryBibleVersion(
                project_id=project_id,
                version=new_version,
                snapshot=StoryBibleService._bible_to_dict(existing),
            )
        )
        await session.flush()
        return existing

    @staticmethod
    async def get_bible(session: AsyncSession, project_id: uuid.UUID, version: int | None = None) -> StoryBible | None:
        if version is None:
            return await StoryBibleService._get_bible_by_project(session, project_id)
        result = await session.execute(
            select(StoryBibleVersion).where(
                StoryBibleVersion.project_id == project_id,
                StoryBibleVersion.version == version,
            )
        )
        version_record = result.scalar_one_or_none()
        if version_record is None:
            return None
        bible = StoryBible(project_id=project_id, version=version)
        bible.created_at = version_record.created_at
        bible.updated_at = version_record.created_at
        StoryBibleService._apply_data_to_bible(bible, version_record.snapshot)
        return bible

    @staticmethod
    async def patch_bible(session: AsyncSession, project_id: uuid.UUID, patch: StoryBiblePatchRequest) -> StoryBible:
        bible = await StoryBibleService._get_bible_by_project(session, project_id)
        if bible is None:
            raise ValueError(f"No Story Bible exists for project {project_id}. Build one first.")
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            return bible
        bible.version += 1
        for key, value in updates.items():
            if hasattr(bible, key):
                setattr(bible, key, list(value) if isinstance(value, list) else str(value or ""))
        session.add(
            StoryBibleVersion(
                project_id=project_id,
                version=bible.version,
                snapshot=StoryBibleService._bible_to_dict(bible),
            )
        )
        await session.flush()
        return bible

    @staticmethod
    async def list_versions(session: AsyncSession, project_id: uuid.UUID) -> list[StoryBibleVersion]:
        result = await session.execute(
            select(StoryBibleVersion)
            .where(StoryBibleVersion.project_id == project_id)
            .order_by(StoryBibleVersion.version.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_version_snapshot(session: AsyncSession, project_id: uuid.UUID, version: int) -> dict[str, Any] | None:
        result = await session.execute(
            select(StoryBibleVersion).where(
                StoryBibleVersion.project_id == project_id,
                StoryBibleVersion.version == version,
            )
        )
        record = result.scalar_one_or_none()
        return record.snapshot if record is not None else None

    @staticmethod
    async def _get_bible_by_project(session: AsyncSession, project_id: uuid.UUID) -> StoryBible | None:
        result = await session.execute(select(StoryBible).where(StoryBible.project_id == project_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _bible_to_dict(bible: StoryBible) -> dict[str, Any]:
        return {
            "project_id": str(bible.project_id),
            "version": bible.version,
            "title": bible.title,
            "genre": bible.genre,
            "visual_style": bible.visual_style,
            "aspect_ratio": bible.aspect_ratio,
            "story_summary": bible.story_summary,
            "main_conflict": bible.main_conflict,
            "emotional_tone": bible.emotional_tone,
            "world_setting": bible.world_setting,
            "time_period": bible.time_period,
            "color_palette": list(bible.color_palette or []),
            "composition_language": list(bible.composition_language or []),
            "characters": list(bible.characters or []),
            "scenes": list(bible.scenes or []),
            "props": list(bible.props or []),
            "negative_prompt_rules": list(bible.negative_prompt_rules or []),
        }

    @staticmethod
    def _apply_data_to_bible(bible: StoryBible, data: dict[str, Any]) -> None:
        bible.version = int(data.get("version", bible.version or 1))
        bible.title = str(data.get("title", ""))
        bible.genre = str(data.get("genre", ""))
        bible.visual_style = str(data.get("visual_style", ""))
        bible.aspect_ratio = str(data.get("aspect_ratio", "9:16"))
        bible.story_summary = str(data.get("story_summary", ""))
        bible.main_conflict = str(data.get("main_conflict", ""))
        bible.emotional_tone = str(data.get("emotional_tone", ""))
        bible.world_setting = str(data.get("world_setting", ""))
        bible.time_period = str(data.get("time_period", ""))
        bible.color_palette = list(data.get("color_palette", []))
        bible.composition_language = list(data.get("composition_language", []))
        bible.characters = list(data.get("characters", []))
        bible.scenes = list(data.get("scenes", []))
        bible.props = list(data.get("props", []))
        bible.negative_prompt_rules = list(data.get("negative_prompt_rules", []))
