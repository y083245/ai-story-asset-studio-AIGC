"""Business logic for the Scene Library module.

All database access goes through a single SQLAlchemy AsyncSession.
LLM calls go through the provider adapter.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.id_factory import generate_scene_id, reset_counters
from app.modules.provider_adapter.base import TextGenerationProvider
from app.modules.scene_library.alias_merger import merge_scene_aliases
from app.modules.scene_library.anchor_generator import ensure_anchors_and_enrich
from app.modules.scene_library.models import GenerationTask, Scene, SceneVersion
from app.modules.scene_library.prompt_builder import (
    build_forbidden_elements,
    build_scene_prompts,
    expand_short_name,
    validate_scene_name,
)
from app.modules.scene_library.schemas import (
    CandidateSceneInput,
    ExtractedScene,
    ExtractedScenesResponse,
    SceneUpdateRequest,
)

# Fields that can trigger a version snapshot on update
_VERSIONED_FIELDS: set[str] = {
    "scene_name",
    "scene_type",
    "time_of_day",
    "weather",
    "lighting",
    "mood",
    "color_palette",
    "fixed_anchors",
    "foreground_elements",
    "midground_elements",
    "background_elements",
    "composition_views",
    "forbidden_elements",
    "scene_prompt",
    "empty_scene_prompt",
    "canonical_asset_id",
    "reference_assets",
}


class SceneLibraryService:
    """Stateless scene management service.

    All methods receive an open AsyncSession and a provider instance.
    Callers (router layer) are responsible for converting to Pydantic
    response schemas.
    """

    # ------------------------------------------------------------------
    # Extraction pipeline
    # ------------------------------------------------------------------

    @staticmethod
    async def extract_scenes(
        session: AsyncSession,
        provider: TextGenerationProvider,
        project_id: str,
        candidates: list[CandidateSceneInput],
        use_llm: bool = True,
    ) -> ExtractedScenesResponse:
        """Run the full extraction pipeline for a project.

        1. Merge aliases (dedup)
        2. Validate/expand scene names
        3. Generate fixed anchors, spatial layers, composition views
        4. Build scene_prompt and empty_scene_prompt
        5. Assign scene IDs
        6. Persist to database
        """
        total_candidates = len(candidates)

        # Step 1: Merge aliases
        merged = await merge_scene_aliases(provider, candidates)
        merged_count = total_candidates - len(merged)

        # Step 2: Validate and expand scene names
        validated: list[CandidateSceneInput] = []
        for c in merged:
            is_valid, error, _ = validate_scene_name(c.name)
            if not is_valid:
                expanded = await expand_short_name(provider, c.name, c.description, c.anchors)
                # Re-validate
                is_valid2, _, _ = validate_scene_name(expanded)
                name = expanded if is_valid2 else f"具体{c.name}"
            else:
                name = c.name
            validated.append(
                CandidateSceneInput(
                    name=name,
                    time=c.time,
                    description=c.description,
                    anchors=c.anchors,
                )
            )

        # Step 3: Reset scene ID counters for this project, then assign
        reset_counters(project_id)

        # Sort by frequency/importance (anchors count as proxy)
        validated_sorted = sorted(validated, key=lambda c: len(c.anchors), reverse=True)

        extracted: list[ExtractedScene] = []
        forbidden = build_forbidden_elements()

        for order, candidate in enumerate(validated_sorted):
            scene_id = generate_scene_id(project_id)

            # Step 4: Generate anchors and spatial enrichment
            enriched = await ensure_anchors_and_enrich(provider, candidate, use_llm=use_llm)

            # Step 5: Infer time_of_day, weather, lighting, mood from candidate
            time_of_day = candidate.time or ""
            weather = ""
            lighting = ""
            mood = ""
            scene_type = "室内"

            # Parse description for atmosphere clues
            desc = candidate.description.lower() if candidate.description else ""
            atmosphere_map = {
                "早晨": ("早晨", "", "晨光", "清新"),
                "清晨": ("清晨", "", "晨光", "宁静"),
                "黄昏": ("黄昏", "", "暖金色光线", "温暖"),
                "夜晚": ("夜晚", "", "暗色灯光", "静谧"),
                "晚上": ("夜晚", "", "暗色灯光", "静谧"),
                "深夜": ("深夜", "", "微弱灯光", "昏暗"),
                "午后": ("午后", "", "明亮日光", "慵懒"),
                "正午": ("正午", "", "强烈日光", "明亮"),
                "白天": ("白天", "", "自然日光", "明亮"),
                "阴": ("白天", "阴天", "柔和散射光", "沉闷"),
                "雨": ("白天", "雨天", "灰暗光线", "忧郁"),
                "雪": ("白天", "雪天", "明亮反射光", "纯净"),
                "晴": ("白天", "晴天", "明亮日光", "明朗"),
                "室内": ("", "", "", ""),
                "室外": ("白天", "", "自然日光", "开阔"),
                "户外": ("白天", "", "自然日光", "开阔"),
            }

            for keyword, (tod, wthr, light, md) in atmosphere_map.items():
                if keyword in desc:
                    if tod and not time_of_day:
                        time_of_day = tod
                    if wthr and not weather:
                        weather = wthr
                    if light and not lighting:
                        lighting = light
                    if md and not mood:
                        mood = md

            # Infer scene_type
            if any(
                kw in candidate.name + desc for kw in ["室外", "户外", "街道", "公园", "广场", "花园", "天台", "海边"]
            ):
                scene_type = "室外"

            # Deduce color_palette
            color_palette = _infer_color_palette(time_of_day, mood, scene_type, candidate.name)

            # Step 6: Generate prompts
            scene_prompt, empty_scene_prompt = await build_scene_prompts(
                provider=provider,
                scene_name=candidate.name,
                scene_type=scene_type,
                time_of_day=time_of_day,
                weather=weather,
                lighting=lighting,
                mood=mood,
                color_palette=color_palette,
                anchors=enriched["fixed_anchors"],
                foreground=enriched["foreground_elements"],
                midground=enriched["midground_elements"],
                background=enriched["background_elements"],
                use_llm=use_llm,
            )

            # Step 7: Persist Scene row
            scene = Scene(
                project_id=uuid.UUID(project_id),
                scene_id=scene_id,
                scene_name=candidate.name,
                scene_type=scene_type,
                sort_order=order,
                time_of_day=time_of_day or None,
                weather=weather or None,
                lighting=lighting or None,
                mood=mood or None,
                color_palette=color_palette,
                fixed_anchors=enriched["fixed_anchors"],
                foreground_elements=enriched["foreground_elements"],
                midground_elements=enriched["midground_elements"],
                background_elements=enriched["background_elements"],
                composition_views=enriched["composition_views"],
                forbidden_elements=forbidden,
                scene_prompt=scene_prompt,
                empty_scene_prompt=empty_scene_prompt,
                consistency_score=None,
                reference_assets=None,
            )
            session.add(scene)

            extracted.append(
                ExtractedScene(
                    scene_id=scene_id,
                    scene_name=candidate.name,
                    scene_type=scene_type,
                    time_of_day=time_of_day or None,
                    weather=weather or None,
                    lighting=lighting or None,
                    mood=mood or None,
                    color_palette=color_palette,
                    fixed_anchors=enriched["fixed_anchors"],
                    foreground_elements=enriched["foreground_elements"],
                    midground_elements=enriched["midground_elements"],
                    background_elements=enriched["background_elements"],
                    composition_views=enriched["composition_views"],
                    forbidden_elements=forbidden,
                    scene_prompt=scene_prompt,
                    empty_scene_prompt=empty_scene_prompt,
                    reference_assets=[],
                )
            )

        await session.flush()

        return ExtractedScenesResponse(
            project_id=project_id,
            scenes=extracted,
            merged_count=merged_count,
            total_candidates=total_candidates,
        )

    # ------------------------------------------------------------------
    # List scenes for a project
    # ------------------------------------------------------------------

    @staticmethod
    async def list_scenes(
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> tuple[list[Scene], int]:
        """Return all scenes for a project, sorted by sort_order."""
        count_stmt = select(func.count()).select_from(Scene).where(Scene.project_id == project_id)
        total = (await session.execute(count_stmt)).scalar_one()

        stmt = select(Scene).where(Scene.project_id == project_id).order_by(Scene.sort_order)
        items = (await session.execute(stmt)).scalars().all()

        return list(items), total

    # ------------------------------------------------------------------
    # Get single scene
    # ------------------------------------------------------------------

    @staticmethod
    async def get_scene(
        session: AsyncSession,
        project_id: uuid.UUID,
        scene_id: str,
    ) -> Scene | None:
        """Return a single scene by project_id and scene_id, or None."""
        stmt = select(Scene).where(Scene.project_id == project_id, Scene.scene_id == scene_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Update scene (with version snapshot)
    # ------------------------------------------------------------------

    @staticmethod
    async def update_scene(
        session: AsyncSession,
        project_id: uuid.UUID,
        scene_id: str,
        data: SceneUpdateRequest,
    ) -> Scene:
        """Partial update of a scene. Creates a version snapshot first.

        Only fields that are actually changed (and are in _VERSIONED_FIELDS)
        trigger a version snapshot.
        """
        scene = await SceneLibraryService._require_scene(session, project_id, scene_id)

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return scene

        # Determine which fields actually changed
        changed: list[str] = []
        previous: dict[str, Any] = {}

        for key, new_value in updates.items():
            if key not in _VERSIONED_FIELDS:
                continue
            old_value = getattr(scene, key, None)
            if old_value != new_value:
                changed.append(key)
                previous[key] = old_value

        if changed:
            # Determine next version number
            version_stmt = select(func.max(SceneVersion.version_number)).where(
                SceneVersion.project_id == project_id,
                SceneVersion.scene_id == scene_id,
            )
            max_ver = (await session.execute(version_stmt)).scalar_one_or_none()
            next_version = (max_ver or 0) + 1

            # Save version snapshot
            version = SceneVersion(
                project_id=project_id,
                scene_id=scene_id,
                version_number=next_version,
                changed_fields=changed,
                previous_values=previous,
            )
            session.add(version)

        # Apply updates
        for key, value in updates.items():
            if key == "sort_order":
                continue  # sort_order is managed internally
            if hasattr(scene, key):
                setattr(scene, key, value)

        await session.flush()
        return scene

    # ------------------------------------------------------------------
    # Regenerate scene (create task, don't call M11)
    # ------------------------------------------------------------------

    @staticmethod
    async def regenerate_scene(
        session: AsyncSession,
        project_id: uuid.UUID,
        scene_id: str,
    ) -> GenerationTask:
        """Create a pending regeneration task for a scene.

        The actual work is dispatched by the Workflow module.
        """
        scene = await SceneLibraryService._require_scene(session, project_id, scene_id)

        task = GenerationTask(
            project_id=project_id,
            task_type="scene_regenerate",
            target_id=scene_id,
            status="pending",
            payload={
                "scene_id": scene_id,
                "scene_name": scene.scene_name,
                "scene_prompt": scene.scene_prompt,
                "empty_scene_prompt": scene.empty_scene_prompt,
            },
        )
        session.add(task)
        await session.flush()

        return task

    # ------------------------------------------------------------------
    # Delete a scene
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_scene(
        session: AsyncSession,
        project_id: uuid.UUID,
        scene_id: str,
    ) -> None:
        """Delete a scene and all its versions."""
        scene = await SceneLibraryService._require_scene(session, project_id, scene_id)
        await session.delete(scene)
        await session.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _require_scene(
        session: AsyncSession,
        project_id: uuid.UUID,
        scene_id: str,
    ) -> Scene:
        """Fetch a scene or raise ValueError."""
        s = await SceneLibraryService.get_scene(session, project_id, scene_id)
        if s is None:
            raise ValueError(f"Scene {scene_id!r} not found")
        return s


# ---------------------------------------------------------------------------
# Color palette inference
# ---------------------------------------------------------------------------


def _infer_color_palette(
    time_of_day: str,
    mood: str,
    scene_type: str,
    scene_name: str,
) -> list[str]:
    """Infer a color palette based on atmosphere clues."""
    palette: list[str] = []

    if "夜晚" in time_of_day or "深夜" in time_of_day:
        palette = ["深蓝", "暗紫", "暖黄", "黑"]
    elif "黄昏" in time_of_day:
        palette = ["暖橙", "金", "深紫", "暗红"]
    elif "早晨" in time_of_day:
        palette = ["浅蓝", "暖粉", "淡金", "白"]
    elif "阴" in mood or "沉闷" in mood:
        palette = ["灰", "暗蓝", "墨绿", "褐"]
    elif "雨" in mood or "忧郁" in mood:
        palette = ["灰蓝", "银", "深绿", "褐"]
    elif "室外" in scene_type:
        palette = ["蓝", "绿", "白", "暖黄"]
    else:
        palette = ["暖棕", "米白", "深木色", "柔和金"]

    # Add scene-specific hints
    name_lower = scene_name.lower()
    if any(w in name_lower for w in ["办公室", "公司", "现代"]):
        palette = ["银灰", "白", "深蓝", "玻璃蓝"]
    elif any(w in name_lower for w in ["咖啡", "书店", "温馨"]):
        palette = ["暖棕", "焦糖", "奶油", "深绿"]
    elif any(w in name_lower for w in ["医院", "诊所", "实验室"]):
        palette = ["白", "淡蓝", "银", "浅灰"]

    return palette
