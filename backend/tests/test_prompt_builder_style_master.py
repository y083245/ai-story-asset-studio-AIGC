from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import settings
from app.modules.image_asset.prompt_builder import (
    build_character_image_prompt,
    build_negative_prompt,
    build_prop_image_prompt,
    build_scene_empty_prompt,
)


def test_character_prompt_builder_uses_plan_prompt_and_style_master_negative():
    character = SimpleNamespace(
        name="苏晚晴",
        reference_image_plan=[
            {
                "category": "正面全身",
                "description": "front final prompt from publication",
                "style_id": "cinematic_realistic",
            }
        ],
    )

    prompt, negative = build_character_image_prompt(character, image_type="character_front")

    assert prompt == "front final prompt from publication"
    assert "低清晰度" in negative
    assert "二次元" in negative
    assert "动漫脸" in negative
    assert len(negative) >= 80
    assert negative != "低质量，模糊，变形，多肢，多手指，文字，水印，logo，侧面视角"


def test_character_turnaround_prompt_builder_accepts_synthesized_plan_prompt_without_strict_template():
    character = SimpleNamespace(
        name="苏晚晴",
        reference_image_plan=[
            {
                "category": "三视图",
                "description": "turnaround final prompt from publication",
                "style_id": "cinematic_realistic",
            }
        ],
    )

    prompt, negative = build_character_image_prompt(character, image_type="character_turnaround")

    assert prompt == "turnaround final prompt from publication"
    assert "三视图不是同一人" in negative


def test_character_prompt_builder_falls_back_to_composer_instead_of_field_list():
    character = SimpleNamespace(
        name="顾辰",
        role_type="配角",
        gender="男",
        age="30岁",
        default_outfit="深色西装",
        reference_image_plan=[],
    )

    prompt, negative = build_character_image_prompt(
        character,
        story_bible={"style_id": "cinematic_realistic"},
        image_type="character_front",
    )

    assert len(prompt) > 200
    assert "真人电影级" in prompt
    assert "性别：男，年龄：30岁" not in prompt
    assert "低清晰度" in negative


def test_scene_prompt_builder_uses_final_prompt_directly_and_style_master_negative():
    scene = SimpleNamespace(
        scene_name="雨夜街口",
        empty_scene_prompt="empty scene final prompt from publication",
    )

    prompt, negative = build_scene_empty_prompt(scene, story_bible={"style_id": "cyberpunk"})

    assert prompt == "empty scene final prompt from publication"
    assert "低清晰度" in negative
    assert "可读广告字" in negative
    assert "人物" in negative
    assert len(negative) >= 80
    assert "赛博元素误入" not in negative
    assert negative != "人物，角色，文字，水印，logo，模糊，变形"


def test_scene_prompt_builder_preserves_positional_extra_constraints_compatibility():
    scene = SimpleNamespace(
        scene_name="雨夜街口",
        empty_scene_prompt="empty scene final prompt from publication",
    )

    prompt, negative = build_scene_empty_prompt(scene, {"style_id": "cyberpunk"}, "keep layout")

    assert prompt == "empty scene final prompt from publication keep layout"
    assert "人物" in negative


def test_prop_prompt_builder_uses_final_prompt_directly_and_style_master_negative():
    prop = SimpleNamespace(
        name="量子密钥",
        prop_prompt="prop final prompt from publication",
    )

    prompt, negative = build_prop_image_prompt(prop, story_bible={"style_id": "sci_fi"}, image_type="prop_product")

    assert prompt == "prop final prompt from publication"
    assert "多余道具" in negative
    assert "赛博街巷" in negative
    assert "低清晰度" in negative
    assert len(negative) >= 80
    assert negative != "人物，手，场景，文字，水印，logo，阴影过重"


def test_build_negative_prompt_combines_style_master_library_parts():
    negative = build_negative_prompt("cinematic_realistic", "character_front")

    assert "低清晰度" in negative
    assert "二次元" in negative
    assert "动漫脸" in negative
    assert len(negative) >= 80


def test_scene_and_prop_prompt_builders_fall_back_to_composer_when_prompt_missing():
    scene_prompt, _ = build_scene_empty_prompt(
        SimpleNamespace(scene_name="空港机库", scene_type="室内", fixed_anchors=[]),
        story_bible={"style_id": "sci_fi"},
    )
    prop_prompt, _ = build_prop_image_prompt(
        SimpleNamespace(name="旧怀表", visual_features="银色表壳"),
        story_bible={"style_id": "cinematic_realistic"},
        image_type="prop_product",
    )

    assert len(scene_prompt) > 200
    assert "未来科幻" in scene_prompt
    assert len(prop_prompt) > 200
    assert "真人电影级" in prop_prompt


def test_prompt_builder_uses_visual_style_before_unknown_genre_for_old_story_bible():
    scene_prompt, negative = build_scene_empty_prompt(
        SimpleNamespace(scene_name="空港机库", scene_type="室内", fixed_anchors=[]),
        story_bible={"genre": "小说", "visual_style": "未来科幻电影类"},
    )

    assert "未来科幻" in scene_prompt
    assert "赛博街巷" in negative


def test_prompt_builder_uses_3d_anime_family_when_story_bible_has_no_specific_style_id():
    prompt, negative = build_character_image_prompt(
        SimpleNamespace(name="霓虹猎手", reference_image_plan=[]),
        story_bible={"style_family": "3d_anime", "genre": "赛博朋克"},
        image_type="character_front",
    )

    assert "赛博朋克类_3D动漫版" in prompt
    assert "CG塑料感" not in negative
    assert "真人照片" in negative


def test_prompt_builder_legacy_mode_restores_old_field_list_and_negatives(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "prompt_engine_mode", "legacy")

    character_prompt, character_negative = build_character_image_prompt(
        SimpleNamespace(name="顾辰", gender="男", age="30岁", default_outfit="深色西装", reference_image_plan=[]),
        story_bible={"style_id": "cinematic_realistic"},
        image_type="character_front",
    )
    scene_prompt, scene_negative = build_scene_empty_prompt(
        SimpleNamespace(scene_name="雨夜街口", empty_scene_prompt="empty scene final prompt from publication"),
        story_bible={"style_id": "cyberpunk"},
    )
    prop_prompt, prop_negative = build_prop_image_prompt(
        SimpleNamespace(name="量子密钥", prop_prompt="prop final prompt from publication"),
        story_bible={"style_id": "sci_fi"},
        image_type="prop_product",
    )

    assert character_prompt == "全部为正面站立全身图片，图片人物背景为纯白，纯白背景，角色名称：顾辰，性别：男，年龄：30岁，上身服装：深色西装。"
    assert character_negative == "低质量，模糊，变形，多肢，多手指，文字，水印，logo，侧面视角"
    assert scene_prompt == "empty scene final prompt from publication，必须包含的固定锚点：核心场景结构和布局。"
    assert scene_negative == "人物，角色，文字，水印，logo，模糊，变形"
    assert prop_prompt == "prop final prompt from publication，道具名称：量子密钥。"
    assert prop_negative == "人物，手，场景，文字，水印，logo，阴影过重"
