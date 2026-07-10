from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import settings
from app.modules.template_style.style_master import load_style_master
from app.modules.workflow.publication import (
    _build_characters,
    _build_props,
    _build_scenes,
    _publication_style_id,
    _story_bible_snapshot,
    _synthesize_prompts_where_needed,
)


class _CountingSynthesizer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.active = 0
        self.max_active = 0

    async def synthesize_character_front(
        self, character: dict[str, Any], style: object, story_context: str = ""
    ) -> str:
        return await self._run("front", str(character.get("name")), story_context)

    async def synthesize_character_turnaround(self, character: dict[str, Any], style: object) -> str:
        return await self._run("turnaround", str(character.get("name")), "")

    async def synthesize_scene_empty(self, scene: dict[str, Any], style: object) -> str:
        return await self._run("empty_scene", str(scene.get("name") or scene.get("scene_name")), "")

    async def synthesize_prop_product(self, prop: dict[str, Any], style: object) -> str:
        return await self._run("prop", str(prop.get("name")), "")

    async def _run(self, kind: str, name: str, extra: str) -> str:
        self.calls.append((kind, name))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return f"{kind} final prompt for {name} {extra}".strip()


@pytest.mark.asyncio
async def test_synthesize_prompts_where_needed_calls_only_marked_assets_and_limits_concurrency():
    style = load_style_master("cinematic_realistic")
    synthesizer = _CountingSynthesizer()
    normalized: dict[str, Any] = {
        "story_bible": {"story_summary": "雨夜旧怀表牵出秘密。"},
        "characters": [
            {"name": "苏晚晴", "front_prompt_needs_synthesis": True},
            {"name": "顾辰", "turnaround_prompt_needs_synthesis": True},
            {"name": "林晓", "front_prompt_needs_synthesis": False, "turnaround_prompt_needs_synthesis": False},
        ],
        "scenes": [
            {"name": "雨夜街口", "empty_scene_prompt_needs_synthesis": True},
            {"name": "玻璃办公室", "empty_scene_prompt_needs_synthesis": True},
        ],
        "props": [
            {"name": "旧怀表", "prop_prompt_needs_synthesis": True},
            {"name": "合同", "prop_prompt_needs_synthesis": True},
        ],
    }

    await _synthesize_prompts_where_needed(synthesizer, style, normalized, concurrency=5)

    assert sorted(synthesizer.calls) == sorted(
        [
            ("front", "苏晚晴"),
            ("turnaround", "顾辰"),
            ("empty_scene", "雨夜街口"),
            ("empty_scene", "玻璃办公室"),
            ("prop", "旧怀表"),
            ("prop", "合同"),
        ]
    )
    assert synthesizer.max_active <= 5
    assert normalized["characters"][0]["front_final_prompt"].startswith("front final prompt")
    assert normalized["characters"][1]["turnaround_final_prompt"].startswith("turnaround final prompt")
    assert "front_final_prompt" not in normalized["characters"][2]
    assert normalized["scenes"][0]["empty_scene_final_prompt"].startswith("empty_scene final prompt")
    assert normalized["props"][0]["prop_final_prompt"].startswith("prop final prompt")


def test_publication_builders_prefer_final_prompts_and_use_composer_fallbacks():
    project_id = uuid.uuid4()
    style = load_style_master("cinematic_realistic")
    characters = _build_characters(
        project_id,
        [
            {
                "name": "苏晚晴",
                "role": "主角",
                "front_image_prompt": "short original front",
                "front_final_prompt": "front final prompt from synthesizer",
                "turnaround_prompt": "short original turnaround",
                "turnaround_final_prompt": "turnaround final prompt from synthesizer",
            },
            {"name": "顾辰", "role": "配角"},
        ],
        style_id="cinematic_realistic",
        style_master=style,
    )
    scenes = _build_scenes(
        project_id,
        [
            {
                "name": "雨夜街口",
                "empty_scene_prompt": "short original scene",
                "empty_scene_final_prompt": "empty scene final prompt from synthesizer",
            }
        ],
        style_master=style,
    )
    props = _build_props(
        project_id,
        [
            {
                "name": "旧怀表",
                "visual_features": "银色表壳",
                "prop_prompt": "short original prop",
                "prop_final_prompt": "prop final prompt from synthesizer",
            }
        ],
        {},
        style_master=style,
    )

    assert characters[0].reference_image_plan[0]["description"] == "front final prompt from synthesizer"
    assert characters[0].reference_image_plan[1]["description"] == "turnaround final prompt from synthesizer"
    assert len(characters[1].reference_image_plan[0]["description"]) > 200
    assert "真人电影级" in characters[1].reference_image_plan[0]["description"]
    assert scenes[0].empty_scene_prompt == "empty scene final prompt from synthesizer"
    assert props[0].prop_prompt == "prop final prompt from synthesizer"


def test_publication_style_id_preserves_3d_anime_family_for_specific_templates():
    style_id = _publication_style_id(
        {"style_family": "3d_anime", "genre": "赛博朋克"},
        {},
    )
    style = load_style_master(style_id)
    project_id = uuid.uuid4()
    characters = _build_characters(
        project_id,
        [{"name": "霓虹猎手", "role": "主角"}],
        style_id=style_id,
        style_master=style,
    )
    snapshot = _story_bible_snapshot(
        SimpleNamespace(
            project_id=project_id,
            version=1,
            title="",
            genre="",
            visual_style="",
            aspect_ratio="9:16",
            story_summary="",
            main_conflict="",
            emotional_tone="",
            world_setting="",
            time_period="",
            color_palette=[],
            composition_language=[],
            characters=[],
            scenes=[],
            props=[],
            negative_prompt_rules=[],
        ),
        style_id=style_id,
        style_family="3d_anime",
    )

    assert style_id == "cyberpunk_3d_anime"
    assert characters[0].reference_image_plan[0]["style_id"] == "cyberpunk_3d_anime"
    assert "赛博朋克类_3D动漫版" in characters[0].reference_image_plan[0]["description"]
    assert snapshot["style_id"] == "cyberpunk_3d_anime"
    assert snapshot["style_family"] == "3d_anime"


def test_publication_builders_legacy_mode_ignore_staged_final_prompts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "prompt_engine_mode", "legacy")
    project_id = uuid.uuid4()

    characters = _build_characters(
        project_id,
        [
            {
                "name": "苏晚晴",
                "role": "主角",
                "front_image_prompt": "legacy front prompt",
                "front_final_prompt": "front final prompt from synthesizer",
                "turnaround_prompt": "legacy turnaround prompt",
                "turnaround_final_prompt": "turnaround final prompt from synthesizer",
            }
        ],
        style_id="cinematic_realistic",
    )
    scenes = _build_scenes(
        project_id,
        [
            {
                "name": "雨夜街口",
                "description": "雨夜街口描述",
                "empty_scene_prompt": "legacy scene prompt",
                "empty_scene_final_prompt": "empty scene final prompt from synthesizer",
            }
        ],
    )
    props = _build_props(
        project_id,
        [
            {
                "name": "旧怀表",
                "visual_features": "银色表壳",
                "prop_prompt": "legacy prop prompt",
                "prop_final_prompt": "prop final prompt from synthesizer",
            }
        ],
        {},
    )
    snapshot = _story_bible_snapshot(
        SimpleNamespace(
            project_id=project_id,
            version=1,
            title="",
            genre="",
            visual_style="",
            aspect_ratio="9:16",
            story_summary="",
            main_conflict="",
            emotional_tone="",
            world_setting="",
            time_period="",
            color_palette=[],
            composition_language=[],
            characters=[],
            scenes=[],
            props=[],
            negative_prompt_rules=[],
        )
    )

    assert characters[0].reference_image_plan[0]["description"] == "legacy front prompt"
    assert characters[0].reference_image_plan[1]["description"] == "legacy turnaround prompt"
    assert scenes[0].empty_scene_prompt == "legacy scene prompt"
    assert props[0].prop_prompt == "legacy prop prompt"
    assert "style_id" not in snapshot
