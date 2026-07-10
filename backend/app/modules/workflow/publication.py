"""Publish analysis workflow output into asset library tables."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.character_library.models import Character
from app.modules.image_asset.models import ImageAsset, ImageGenerationTask
from app.modules.image_asset.schemas import GenerateAssetRequest
from app.modules.image_asset.service import ImageAssetService
from app.modules.image_asset.turnaround_template import normalize_turnaround_prompt
from app.modules.observability.prompt_audit import PromptAuditRecord, write_prompt_audit_record
from app.modules.prop_library.models import Prop
from app.modules.provider_adapter.registry import ProviderRegistry
from app.modules.scene_library.models import Scene
from app.modules.storage.service import StorageService
from app.modules.story_bible.models import StoryBible, StoryBibleVersion
from app.modules.template_style.style_alias import normalize_style_id_for_family
from app.modules.template_style.style_master import StyleMasterProfile, load_style_master
from app.modules.workflow.asset_pipeline import AssetGenerationPlan, AssetPipelinePlanner, AssetStage
from app.modules.workflow.prompt_composer import (
    compose_character_front,
    compose_character_turnaround,
    compose_prop_product,
    compose_scene_empty,
)
from app.modules.workflow.prompt_synthesizer import PromptSynthesizer

logger = logging.getLogger("storyasset.workflow.publication")


class AnalysisPublicationService:
    """Materialize analysis output into editable libraries."""

    @staticmethod
    async def publish(
        session: AsyncSession,
        project_id: uuid.UUID,
        context: dict[str, Any],
        *,
        generate_images: bool = True,
    ) -> dict[str, Any]:
        normalized = _normalize_context(project_id, context)
        staged = settings.prompt_engine_mode == "staged"
        style_master = load_style_master(normalized["style_id"]) if staged else None
        if staged and style_master is not None:
            await _synthesize_prompts_where_needed(PromptSynthesizer(), style_master, normalized)
        await _delete_generated_rows(session, project_id)

        characters = _build_characters(
            project_id,
            normalized["characters"],
            style_id=normalized["style_id"],
            style_master=style_master,
        )
        character_name_to_id = {item.name: item.character_id for item in characters}
        scenes = _build_scenes(project_id, normalized["scenes"], style_master=style_master)
        props = _build_props(project_id, normalized["props"], character_name_to_id, style_master=style_master)
        _audit_published_prompts(project_id, characters=characters, scenes=scenes, props=props)
        story_bible = await _upsert_story_bible(
            session=session,
            project_id=project_id,
            normalized=normalized,
            characters=characters,
            scenes=scenes,
            props=props,
        )

        for item in [*characters, *scenes, *props]:
            session.add(item)
        await session.flush()

        asset_summary = {"assets": 0, "asset_errors": []}
        if generate_images:
            asset_summary = await _generate_reference_assets(
                session=session,
                project_id=project_id,
                characters=characters,
                scenes=scenes,
                props=props,
            )

        session.add(
            StoryBibleVersion(
                project_id=project_id,
                version=story_bible.version,
                snapshot=_story_bible_snapshot(
                    story_bible,
                    style_id=normalized["style_id"] if staged else "",
                    style_family=_text(normalized["genre_result"].get("style_family")) if staged else "",
                ),
            )
        )
        await session.flush()
        return {
            "story_bible_version": story_bible.version,
            "characters": len(characters),
            "scenes": len(scenes),
            "props": len(props),
            **asset_summary,
        }


async def _delete_generated_rows(session: AsyncSession, project_id: uuid.UUID) -> None:
    for stmt in (
        delete(ImageAsset).where(ImageAsset.project_id == project_id),
        delete(ImageGenerationTask).where(ImageGenerationTask.project_id == project_id),
        delete(Prop).where(Prop.project_id == project_id),
        delete(Scene).where(Scene.project_id == project_id),
        delete(Character).where(Character.project_id == project_id),
    ):
        await session.execute(stmt)
    await session.flush()


def _normalize_context(project_id: uuid.UUID, context: dict[str, Any]) -> dict[str, Any]:
    genre = _dict(context.get("genre_result"))
    story = _dict(context.get("story_bible"))
    return {
        "project_id": str(project_id),
        "aspect_ratio": _text(context.get("aspect_ratio"), "9:16"),
        "genre_result": genre,
        "style_id": _publication_style_id(genre, story),
        "story_bible": story,
        "characters": _as_list(context.get("characters")),
        "scenes": _as_list(context.get("scenes")),
        "props": _as_list(context.get("props")),
    }


def _publication_style_id(genre_result: dict[str, Any], story_bible: dict[str, Any]) -> str:
    raw = genre_result.get("style_id") or story_bible.get("style_id") or genre_result.get("genre")
    style_family = genre_result.get("style_family") or story_bible.get("style_family")
    return normalize_style_id_for_family(str(raw or ""), str(style_family or ""))


async def _synthesize_prompts_where_needed(
    synthesizer: PromptSynthesizer,
    style: StyleMasterProfile,
    normalized: dict[str, Any],
    *,
    concurrency: int | None = None,
) -> None:
    """Synthesize final image prompts for assets marked by normalizers."""
    semaphore = asyncio.Semaphore(max(1, concurrency or settings.prompt_synthesizer_concurrency))
    story = _dict(normalized.get("story_bible"))
    story_context = _text(story.get("story_summary") or story.get("summary"))

    async def run_one(kind: str, item: dict[str, Any]) -> None:
        async with semaphore:
            try:
                if kind == "front":
                    item["front_final_prompt"] = await synthesizer.synthesize_character_front(item, style, story_context)
                elif kind == "turnaround":
                    item["turnaround_final_prompt"] = await synthesizer.synthesize_character_turnaround(item, style)
                elif kind == "empty_scene":
                    item["empty_scene_final_prompt"] = await synthesizer.synthesize_scene_empty(item, style)
                elif kind == "prop":
                    item["prop_final_prompt"] = await synthesizer.synthesize_prop_product(item, style)
            except Exception as exc:
                logger.warning(
                    "Prompt synthesis failed kind=%s name=%s error_type=%s",
                    kind,
                    item.get("name"),
                    exc.__class__.__name__,
                )
                if kind == "front":
                    item["front_final_prompt"] = compose_character_front(item, style)
                elif kind == "turnaround":
                    item["turnaround_final_prompt"] = compose_character_turnaround(item, style)
                elif kind == "empty_scene":
                    item["empty_scene_final_prompt"] = compose_scene_empty(item, style)
                elif kind == "prop":
                    item["prop_final_prompt"] = compose_prop_product(item, style)

    tasks: list[asyncio.Task[None]] = []
    for character in normalized.get("characters", []):
        item = _dict(character)
        if item.get("front_prompt_needs_synthesis"):
            tasks.append(asyncio.create_task(run_one("front", item)))
        if item.get("turnaround_prompt_needs_synthesis"):
            tasks.append(asyncio.create_task(run_one("turnaround", item)))
    for scene in normalized.get("scenes", []):
        item = _dict(scene)
        if item.get("empty_scene_prompt_needs_synthesis"):
            tasks.append(asyncio.create_task(run_one("empty_scene", item)))
    for prop in normalized.get("props", []):
        item = _dict(prop)
        if item.get("prop_prompt_needs_synthesis"):
            tasks.append(asyncio.create_task(run_one("prop", item)))
    if tasks:
        await asyncio.gather(*tasks)


def _build_characters(
    project_id: uuid.UUID,
    items: list[Any],
    *,
    style_id: str,
    style_master: StyleMasterProfile | None = None,
) -> list[Character]:
    characters: list[Character] = []
    used_ids: set[str] = set()
    staged = settings.prompt_engine_mode == "staged"
    style = style_master if staged else None
    for index, raw_item in enumerate(items, start=1):
        item = _dict(raw_item)
        character_id = _stable_id(item, ("character_id", "id"), "CH", index, used_ids)
        name = _clamp(item.get("name"), 100, f"角色{index}")
        role = _normalize_cn_role(_text(item.get("role") or item.get("role_type"), "配角"))
        age = _clamp(item.get("age_range") or item.get("age"), 20)
        gender = _optional_clamp(item.get("gender"), 10)
        description = _text(item.get("description") or item.get("personality"))
        outfit = _text(item.get("default_outfit") or item.get("outfit"), "符合角色身份的具体服装")
        front_prompt = (
            _optional_text(item.get("front_final_prompt")) or _optional_text(item.get("front_image_prompt"))
            if staged
            else _optional_text(item.get("front_image_prompt"))
        )
        turnaround_prompt = (
            _optional_text(item.get("turnaround_final_prompt")) or _optional_text(item.get("turnaround_prompt"))
            if staged
            else _optional_text(item.get("turnaround_prompt"))
        )
        consistency_tag = f"name={name}，role={role}，gender={gender or ''}，age={age}，outfit={outfit}"
        composer_character = {
            **item,
            "name": name,
            "role": role,
            "gender": gender or "",
            "age": age,
            "description": description,
            "default_outfit": outfit,
        }
        characters.append(
            Character(
                project_id=project_id,
                character_id=character_id,
                name=name,
                aliases=_string_list(item.get("aliases")) or None,
                role_type=role,
                sort_order=index - 1,
                gender=gender,
                age=age or None,
                height=_optional_clamp(item.get("height"), 20),
                body_type=_optional_clamp(item.get("body_type"), 30),
                face_shape=_optional_clamp(item.get("face_shape"), 30),
                facial_bone_structure=_optional_clamp(item.get("facial_features"), 50),
                skin_tone=_optional_clamp(item.get("skin_tone"), 30),
                eyes=_optional_clamp(item.get("eyes"), 50),
                eyebrows=_optional_clamp(item.get("eyebrows"), 30),
                nose=_optional_clamp(item.get("nose"), 50),
                mouth=_optional_clamp(item.get("mouth"), 50),
                hair_color=_optional_clamp(item.get("hair_color"), 30),
                hair_style=_optional_clamp(item.get("hair_style"), 100),
                default_outfit=outfit,
                outfit_details=_optional_text(item.get("outfit_details")),
                shoes=_optional_clamp(item.get("shoes"), 100),
                accessories=_optional_clamp(item.get("accessories"), 200),
                identity=_optional_clamp(item.get("identity"), 200),
                personality=description or None,
                first_appearance=_optional_clamp(item.get("first_appearance"), 100),
                emotion_pack=[],
                consistency_tag=consistency_tag,
                forbidden_changes=_string_list(item.get("forbidden_changes")) or ["姓名", "发型", "服装主色", "关键配饰"],
                reference_image_plan=_character_image_plan(
                    name=name,
                    role=role,
                    gender=gender,
                    age=age,
                    description=description,
                    outfit=outfit,
                    front_prompt=front_prompt,
                    turnaround_prompt=turnaround_prompt,
                    style_id=style_id,
                    style_master=style,
                    character_data=composer_character,
                ),
                reference_assets=[],
            )
        )
    return characters


def _audit_published_prompts(
    project_id: uuid.UUID,
    *,
    characters: list[Character],
    scenes: list[Scene],
    props: list[Prop],
) -> None:
    with contextlib.suppress(Exception):
        for character in characters:
            for asset_type, prompt in (
                ("character_front", character.front_prompt),
                ("character_turnaround", character.turnaround_prompt),
            ):
                write_prompt_audit_record(
                    PromptAuditRecord(
                        project_id=str(project_id),
                        entity_type="character",
                        entity_id=character.character_id,
                        asset_type=asset_type,
                        stage="publication_final_prompt",
                        source_prompt=prompt or "",
                        final_prompt=prompt or "",
                    )
                )
        for scene in scenes:
            write_prompt_audit_record(
                PromptAuditRecord(
                    project_id=str(project_id),
                    entity_type="scene",
                    entity_id=scene.scene_id,
                    asset_type="scene_empty",
                    stage="publication_final_prompt",
                    source_prompt=scene.empty_scene_prompt or "",
                    final_prompt=scene.empty_scene_prompt or "",
                )
            )
        for prop in props:
            write_prompt_audit_record(
                PromptAuditRecord(
                    project_id=str(project_id),
                    entity_type="prop",
                    entity_id=prop.prop_id,
                    asset_type="prop_product",
                    stage="publication_final_prompt",
                    source_prompt=prop.prop_prompt or "",
                    final_prompt=prop.prop_prompt or "",
                )
            )


def _build_scenes(
    project_id: uuid.UUID,
    items: list[Any],
    *,
    style_master: StyleMasterProfile | None = None,
) -> list[Scene]:
    scenes: list[Scene] = []
    used_ids: set[str] = set()
    staged = settings.prompt_engine_mode == "staged"
    style = style_master if staged else None
    for index, raw_item in enumerate(items, start=1):
        item = _dict(raw_item)
        scene_id = _stable_id(item, ("scene_id", "id"), "SC", index, used_ids)
        name = _clamp(item.get("scene_name") or item.get("name"), 100, f"场景{index}")
        description = _text(item.get("description"), name)
        if staged:
            empty_scene_prompt = (
                _optional_text(item.get("empty_scene_final_prompt"))
                or _optional_text(item.get("empty_scene_prompt"))
                or compose_scene_empty(
                    {**item, "name": name, "description": description},
                    style or load_style_master("cinematic_realistic"),
                )
            )
        else:
            empty_scene_prompt = _text(item.get("empty_scene_prompt"), description)
        scenes.append(
            Scene(
                project_id=project_id,
                scene_id=scene_id,
                scene_name=name,
                scene_type=_clamp(item.get("scene_type") or item.get("type"), 50, "室内"),
                sort_order=index - 1,
                time_of_day=_optional_clamp(item.get("time_of_day") or item.get("time"), 30),
                weather=_optional_clamp(item.get("weather"), 30),
                lighting=_optional_clamp(item.get("lighting"), 100),
                mood=_optional_clamp(item.get("mood"), 100),
                color_palette=_string_list(item.get("color_palette")),
                fixed_anchors=_string_list(item.get("fixed_anchors") or item.get("anchors")) or [name],
                foreground_elements=_string_list(item.get("foreground_elements")),
                midground_elements=_string_list(item.get("midground_elements")),
                background_elements=_string_list(item.get("background_elements")),
                composition_views=_string_list(item.get("composition_views")),
                forbidden_elements=_string_list(item.get("forbidden_elements")) or ["人物", "文字", "水印", "logo"],
                scene_prompt=_text(item.get("scene_prompt") or item.get("prompt"), description),
                empty_scene_prompt=empty_scene_prompt,
                consistency_score=None,
                reference_assets=[],
            )
        )
    return scenes


def _build_props(
    project_id: uuid.UUID,
    items: list[Any],
    character_name_to_id: dict[str, str],
    *,
    style_master: StyleMasterProfile | None = None,
) -> list[Prop]:
    props: list[Prop] = []
    used_ids: set[str] = set()
    staged = settings.prompt_engine_mode == "staged"
    style = style_master if staged else None
    for index, raw_item in enumerate(items, start=1):
        item = _dict(raw_item)
        prop_id = _stable_id(item, ("prop_id", "id"), "PR", index, used_ids)
        owner_id = _optional_clamp(item.get("owner_character_id"), 20) or character_name_to_id.get(
            _text(item.get("owner_name"))
        )
        visual = _text(item.get("visual_features") or item.get("description"), f"道具{index}")
        if staged:
            prop_prompt = (
                _optional_text(item.get("prop_final_prompt"))
                or _optional_text(item.get("prop_prompt"))
                or compose_prop_product(
                    {**item, "name": _clamp(item.get("name"), 100, f"道具{index}"), "visual_features": visual},
                    style or load_style_master("cinematic_realistic"),
                )
            )
        else:
            prop_prompt = _text(item.get("prop_prompt"), visual)
        props.append(
            Prop(
                project_id=project_id,
                prop_id=prop_id,
                name=_clamp(item.get("name"), 100, f"道具{index}"),
                aliases=_string_list(item.get("aliases")) or None,
                importance=_normalize_importance(_text(item.get("importance")), index),
                category=_optional_clamp(item.get("category") or item.get("type"), 50),
                owner_character_id=owner_id,
                visual_features=visual,
                material=_optional_clamp(item.get("material"), 100),
                color=_optional_clamp(item.get("color"), 100),
                size=_optional_clamp(item.get("size"), 50),
                first_appearance=_optional_clamp(item.get("first_appearance"), 200),
                plot_function=_optional_text(item.get("plot_function") or item.get("function")),
                state_timeline=_normalize_state_timeline(item.get("state_timeline")),
                prop_prompt=prop_prompt,
                usage_prompt=_text(item.get("usage_prompt"), visual),
                reference_assets=[],
            )
        )
    return props


async def _upsert_story_bible(
    *,
    session: AsyncSession,
    project_id: uuid.UUID,
    normalized: dict[str, Any],
    characters: list[Character],
    scenes: list[Scene],
    props: list[Prop],
) -> StoryBible:
    result = await session.execute(select(StoryBible).where(StoryBible.project_id == project_id))
    bible = result.scalar_one_or_none()
    if bible is None:
        bible = StoryBible(project_id=project_id, version=1)
        session.add(bible)
    else:
        bible.version += 1

    story = normalized["story_bible"]
    genre = normalized["genre_result"]
    bible.title = _text(story.get("title"), "AI 资产图项目")
    bible.genre = _text(genre.get("genre") or story.get("genre"), "小说")
    bible.visual_style = _text(story.get("visual_style"), " / ".join(_string_list(genre.get("style_tags"))) or "视觉资产图")
    bible.aspect_ratio = normalized["aspect_ratio"]
    bible.story_summary = _text(story.get("story_summary") or story.get("summary"), "故事摘要待补充")
    bible.main_conflict = _text(story.get("main_conflict"), "")
    bible.emotional_tone = _text(story.get("emotional_tone"), "")
    bible.world_setting = _text(story.get("world_setting"), "")
    bible.time_period = _text(story.get("time_period"), "")
    bible.color_palette = _string_list(story.get("color_palette"))
    bible.composition_language = _string_list(story.get("composition_language"))
    bible.characters = [{"character_id": c.character_id, "name": c.name, "role": c.role_type} for c in characters]
    bible.scenes = [{"scene_id": s.scene_id, "scene_name": s.scene_name, "type": s.scene_type} for s in scenes]
    bible.props = [{"prop_id": p.prop_id, "name": p.name, "importance": p.importance} for p in props]
    bible.negative_prompt_rules = [{"rule": "文字，水印，logo，低质量，模糊，变形", "applies_to": "image"}]
    await session.flush()
    return bible


async def _generate_reference_assets(
    *,
    session: AsyncSession,
    project_id: uuid.UUID,
    characters: list[Character],
    scenes: list[Scene],
    props: list[Prop],
) -> dict[str, Any]:
    service = ImageAssetService(
        image_provider=ProviderRegistry().get_image_generator(),
        storage_service=StorageService.create(),
    )
    asset_count = 0
    errors: list[dict[str, str]] = []

    async def generate_one(owner: Any | None, request: GenerateAssetRequest, *, canonical: bool = False) -> str | None:
        nonlocal asset_count
        try:
            response = await service.generate_asset(request, session)
            asset_count += 1
            _append_reference_asset(owner, response.storage_path)
            if canonical and owner is not None and hasattr(owner, "canonical_asset_id"):
                owner.canonical_asset_id = response.storage_path
            return response.storage_path
        except Exception as exc:
            logger.warning(
                "Reference asset generation failed asset_type=%s related_id=%s: %s",
                request.asset_type,
                request.related_id,
                exc,
            )
            errors.append({"asset_type": request.asset_type, "related_id": request.related_id or "", "error": str(exc)})
            return None

    if settings.reference_chain_enabled:
        planner = AssetPipelinePlanner()
        character_canonical: dict[str, str] = {}
        for character in characters:
            plan = planner.plan_character_pipeline(character)
            stage_paths = await _run_asset_plan(
                plan=plan,
                owner=character,
                project_id=project_id,
                generate_one=generate_one,
                errors=errors,
            )
            if character.canonical_asset_id:
                character_canonical[character.character_id] = character.canonical_asset_id
            elif stage_paths.get("bible_sheet"):
                character_canonical[character.character_id] = stage_paths["bible_sheet"]

        for scene in scenes:
            await _run_asset_plan(
                plan=planner.plan_scene_pipeline(scene),
                owner=scene,
                project_id=project_id,
                generate_one=generate_one,
                errors=errors,
            )

        for prop in props:
            extra_references: dict[str, list[str]] = {}
            owner_character_id = getattr(prop, "owner_character_id", None)
            if owner_character_id and owner_character_id in character_canonical:
                extra_references["prop_usage"] = [character_canonical[owner_character_id]]
            await _run_asset_plan(
                plan=planner.plan_prop_pipeline(prop),
                owner=prop,
                project_id=project_id,
                generate_one=generate_one,
                errors=errors,
                extra_references=extra_references,
            )

        await session.flush()
        return {"assets": asset_count, "asset_errors": errors}

    for character in characters:
        front_path = await generate_one(
            character,
            GenerateAssetRequest(project_id=project_id, asset_type="character_front", related_id=character.character_id),
        )
        await generate_one(
            character,
            GenerateAssetRequest(
                project_id=project_id,
                asset_type="character_turnaround",
                related_id=character.character_id,
                reference_asset_ids=[front_path] if front_path else [],
            ),
        )

    for scene in scenes:
        await generate_one(scene, GenerateAssetRequest(project_id=project_id, asset_type="scene_empty", related_id=scene.scene_id))

    for prop in props:
        await generate_one(prop, GenerateAssetRequest(project_id=project_id, asset_type="prop_product", related_id=prop.prop_id))

    await session.flush()
    return {"assets": asset_count, "asset_errors": errors}


async def _run_asset_plan(
    *,
    plan: AssetGenerationPlan,
    owner: Any,
    project_id: uuid.UUID,
    generate_one: Any,
    errors: list[dict[str, str]],
    extra_references: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    stage_paths: dict[str, str] = {}
    extra_references = extra_references or {}
    for stage in plan.stages:
        reference_asset_ids = _reference_asset_ids_for_stage(stage, stage_paths)
        reference_asset_ids.extend(extra_references.get(stage.stage_name, []))
        reference_asset_ids = _dedupe(reference_asset_ids)
        missing_references = [name for name in stage.reference_stages if name not in stage_paths]
        if missing_references:
            errors.append(
                {
                    "asset_type": stage.asset_type,
                    "related_id": plan.entity_id,
                    "error": f"Missing reference stages: {', '.join(missing_references)}",
                }
            )
            continue
        storage_path = await generate_one(
            owner,
            GenerateAssetRequest(
                project_id=project_id,
                asset_type=stage.asset_type,
                related_id=plan.entity_id,
                reference_asset_ids=reference_asset_ids,
            ),
            canonical=stage.priority == 0,
        )
        if storage_path:
            stage_paths[stage.stage_name] = storage_path
    return stage_paths


def _reference_asset_ids_for_stage(stage: AssetStage, stage_paths: dict[str, str]) -> list[str]:
    return [stage_paths[name] for name in stage.reference_stages if name in stage_paths]


def _append_reference_asset(owner: Any | None, storage_path: str) -> None:
    if owner is None or not hasattr(owner, "reference_assets"):
        return
    reference_assets = list(owner.reference_assets or [])
    if storage_path not in reference_assets:
        reference_assets.append(storage_path)
        owner.reference_assets = reference_assets


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _story_bible_snapshot(bible: StoryBible, *, style_id: str = "", style_family: str = "") -> dict[str, Any]:
    snapshot = {
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
        "color_palette": bible.color_palette,
        "composition_language": bible.composition_language,
        "characters": bible.characters,
        "scenes": bible.scenes,
        "props": bible.props,
        "negative_prompt_rules": bible.negative_prompt_rules,
    }
    if style_id:
        snapshot["style_id"] = style_id
    if style_family:
        snapshot["style_family"] = style_family
    return snapshot


def _character_image_plan(
    *,
    name: str,
    role: str,
    gender: str | None,
    age: str,
    description: str,
    outfit: str,
    front_prompt: str | None,
    turnaround_prompt: str | None,
    style_id: str,
    style_master: StyleMasterProfile | None = None,
    character_data: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    fallback_character_description = (
        f"角色名称：{name}，角色定位：{role}，性别：{gender or ''}，年龄：{age}，形象：{description}，服装：{outfit}"
    )
    if settings.prompt_engine_mode == "legacy":
        front = front_prompt or (
            f"纯白背景，正面站立全身图，角色名称：{name}，角色定位：{role}，"
            f"性别：{gender or ''}，年龄：{age}，形象：{description}，服装：{outfit}。"
        )
        turn = turnaround_prompt or normalize_turnaround_prompt(
            fallback_character_description,
            fallback_character_description,
            style_id=style_id,
        )
        return [
            {"category": "正面全身", "description": front, "style_id": style_id},
            {"category": "三视图", "description": turn, "style_id": style_id},
        ]

    style = style_master or load_style_master(style_id)
    data = character_data or {
        "name": name,
        "role": role,
        "gender": gender or "",
        "age": age,
        "description": description,
        "default_outfit": outfit,
    }
    front = front_prompt or compose_character_front(data, style)
    turn = turnaround_prompt or compose_character_turnaround({**data, "description": fallback_character_description}, style)
    return [
        {"category": "正面全身", "description": front, "style_id": style_id},
        {"category": "三视图", "description": turn, "style_id": style_id},
    ]


def _stable_id(item: dict[str, Any], keys: tuple[str, ...], prefix: str, index: int, used: set[str]) -> str:
    for key in keys:
        value = str(item.get(key) or "").strip()
        if value and value not in used:
            used.add(value)
            return value
    while True:
        candidate = f"{prefix}_{index:03d}"
        index += 1
        if candidate not in used:
            used.add(candidate)
            return candidate


def _normalize_cn_role(value: str) -> str:
    if value in {"主角", "配角", "反派", "路人"}:
        return value
    if value.lower() in {"lead", "protagonist", "main"}:
        return "主角"
    if value.lower() in {"villain", "antagonist"}:
        return "反派"
    return "配角"


def _normalize_importance(value: str, index: int) -> str:
    allowed = {"core", "supporting", "minor"}
    if value in allowed:
        return value
    return "core" if index == 1 else "supporting"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_state_timeline(value: Any) -> list[dict[str, object]]:
    timeline: list[dict[str, object]] = []
    for index, raw_item in enumerate(_as_list(value), start=1):
        if isinstance(raw_item, dict):
            state = _text(raw_item.get("state") or raw_item.get("description"))
            description = _text(raw_item.get("description") or state)
            try:
                step_index = int(raw_item.get("step_index") or raw_item.get("step") or index)
            except (TypeError, ValueError):
                step_index = index
            if state or description:
                timeline.append(
                    {
                        "step_index": max(step_index, 1),
                        "state": state or description,
                        "description": description or state,
                    }
                )
            continue

        text = _text(raw_item)
        if text:
            timeline.append({"step_index": index, "state": text, "description": text})
    return timeline


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clamp(value: Any, limit: int, default: str = "") -> str:
    return _text(value, default)[:limit]


def _optional_clamp(value: Any, limit: int) -> str | None:
    text = _optional_text(value)
    return text[:limit] if text else None
