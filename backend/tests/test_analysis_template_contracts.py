from __future__ import annotations

import uuid

import pytest

from app.config import settings
from app.modules.template_style.style_pack import StylePackTemplate
from app.modules.workflow.analysis_activities import (
    _normalize_characters,
    _normalize_props,
    _normalize_scenes,
    _render_prompt,
)
from app.modules.workflow.normalizers.genre import normalize_confidence, normalize_genre
from app.modules.workflow.prompt_render import render_system_prompt
from app.modules.workflow.service import _analysis_response_from_context


def _template(module_id: str = "character_extractor") -> StylePackTemplate:
    return StylePackTemplate(
        style_id="urban_drama",
        style_name="都市短剧类",
        module_id=module_id,
        source_master="test",
        system_prompt="system",
        user_prompt_template="小说正文：{{ text }}\n风格：{{ style_name }}\n上下文：{{ context_json }}",
    )


def test_render_prompt_embeds_exact_story_engine_contract_before_novel_text():
    rendered = _render_prompt(
        _template(),
        text="她拿着合同走进会议室。",
        context={"style_id": "urban_drama"},
        template_contract="【本风格关键词】现代都市短剧、合同、病历",
    )

    assert "【后端已读取的风格模板原文】" in rendered
    assert "【本风格关键词】现代都市短剧、合同、病历" in rendered
    assert "必须严格按上方风格模板原文提取" in rendered
    assert rendered.index("【后端已读取的风格模板原文】") < rendered.index("小说正文：她拿着合同走进会议室。")


def test_render_prompt_replaces_garbled_3d_style_pack_text_with_readable_fallback():
    template = StylePackTemplate(
        style_id="cyberpunk_3d_anime",
        style_name="?????_3D???",
        module_id="genre_detector",
        source_master="test",
        system_prompt="?????????????????????????????? JSON?",
        user_prompt_template="?????????????????\n\n{{ text }}\n??? JSON?",
    )

    rendered = _render_prompt(
        template,
        text="全片目标是 3D 动漫赛博朋克视觉，霓虹街区和机械义体。",
        context={"style_id": "cyberpunk_3d_anime"},
        template_contract="style_family=3d_anime\nstyle_id=cyberpunk_3d_anime\n赛博朋克类_3D动漫版",
    )
    system_prompt = render_system_prompt(template)

    assert "????" not in rendered
    assert "????" not in system_prompt
    assert "style_family=3d_anime" in rendered
    assert "style_id=cyberpunk_3d_anime" in rendered
    assert "小说文本" in system_prompt


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.95, 0.95),
        (95, 0.95),
        ("95%", 0.95),
        (1.2, 1.0),
        (-3, 0.0),
        (250, 1.0),
        ("bad", 0.0),
    ],
)
def test_normalize_confidence_accepts_decimal_percent_and_invalid_values(raw: object, expected: float):
    assert normalize_confidence(raw) == expected


def test_normalize_genre_preserves_style_family_and_clamps_confidence():
    genre = normalize_genre(
        {
            "genre": "都市商战",
            "style_family": "realistic",
            "style_id": "urban_drama_live_action_realistic",
            "confidence": "95%",
            "evidence": ["现代商业空间", "真人写实服装材质"],
            "risk": "与真人电影级接近",
        }
    )

    assert genre["style_id"] == "urban_drama"
    assert genre["style_family"] == "realistic"
    assert genre["confidence"] == 0.95
    assert genre["evidence"] == ["现代商业空间", "真人写实服装材质"]
    assert genre["risk"] == "与真人电影级接近"


@pytest.mark.parametrize(
    ("genre_name", "expected_style_id"),
    [
        ("都市爱情", "urban_drama_3d_anime"),
        ("中国古风", "chinese_historical_3d_anime"),
        ("古风仙侠", "xianxia_3d_anime"),
        ("未来科幻", "future_scifi_movie_3d_anime"),
        ("真人电影级", "cinematic_live_action_3d_anime"),
        ("赛博朋克", "cyberpunk_3d_anime"),
    ],
)
def test_normalize_genre_keeps_3d_anime_family_from_falling_back_to_realistic(
    genre_name: str, expected_style_id: str
):
    genre = normalize_genre(
        {
            "genre": genre_name,
            "style_family": "3d_anime",
            "confidence": 0.91,
        }
    )

    assert genre["style_family"] == "3d_anime"
    assert genre["style_id"] == expected_style_id


def test_analysis_response_from_context_normalizes_legacy_percent_confidence():
    response = _analysis_response_from_context(
        uuid.uuid4(),
        {
            "genre_result": {
                "genre": "都市商战",
                "style_tags": ["都市", "真人写实"],
                "confidence": 95,
            },
            "story_bible": {},
            "characters": [],
            "scenes": [],
            "props": [],
        },
    )

    assert response["style_confidence"] == 0.95


def test_normalize_characters_marks_invalid_prompts_for_synthesis_without_rewriting():
    characters = _normalize_characters(
        [
            {
                "name": "林晓",
                "role": "主角",
                "gender": "女",
                "age_range": "25岁",
                "description": "职场新人，冷静克制",
                "default_outfit": "白色衬衫搭配深色西装裤",
                "front_image_prompt": "白色衬衫搭配深色西装裤，冷白办公室灯光。",
                "turnaround_prompt": "背影设定参考，保持白色衬衫和深色西装裤。",
            }
        ],
        style_id="urban_drama",
    )

    item = characters[0]
    assert item["front_image_prompt"] == "白色衬衫搭配深色西装裤，冷白办公室灯光。"
    assert item["front_prompt_needs_synthesis"] is True
    assert item["turnaround_prompt"] == "背影设定参考，保持白色衬衫和深色西装裤。"
    assert item["turnaround_prompt_needs_synthesis"] is True
    assert item["forbidden_changes"]


def test_normalize_characters_accepts_compliant_prompts_without_rewriting():
    characters = _normalize_characters(
        [
            {
                "name": "林晓",
                "front_image_prompt": "正面站立全身角色资产图，白色衬衫搭配深色西装裤。",
                "turnaround_prompt": "角色三视图，正面、侧面、背面保持同一服装和发型。",
            }
        ],
        style_id="urban_drama",
    )

    item = characters[0]
    assert item["front_image_prompt"] == "正面站立全身角色资产图，白色衬衫搭配深色西装裤。"
    assert item["front_prompt_needs_synthesis"] is False
    assert item["turnaround_prompt"] == "角色三视图，正面、侧面、背面保持同一服装和发型。"
    assert item["turnaround_prompt_needs_synthesis"] is False


def test_normalize_characters_rejects_non_front_full_body_false_positives():
    characters = _normalize_characters(
        [
            {"name": "林晓", "front_image_prompt": "全身背影设定，白色衬衫搭配深色西装裤。"},
            {"name": "顾辰", "front_image_prompt": "完整人物侧面图，深色西装，皮鞋清楚。"},
            {"name": "周远", "front_image_prompt": "front view portrait, navy jacket."},
        ],
        style_id="urban_drama",
    )

    assert [item["front_prompt_needs_synthesis"] for item in characters] == [True, True, True]


def test_normalize_scenes_preserves_prompt_and_marks_empty_scene_synthesis_need():
    scenes = _normalize_scenes(
        [
            {
                "name": "办公室",
                "scene_type": "室内",
                "description": "林晓站在玻璃会议室里，桌上放着合同。",
                "empty_scene_prompt": "玻璃会议室，冷白光。",
            }
        ],
        style_id="urban_drama",
    )

    item = scenes[0]
    assert len(item["name"]) >= 4
    assert item["empty_scene_prompt"] == "玻璃会议室，冷白光。"
    assert item["empty_scene_prompt_needs_synthesis"] is True
    assert len(item["fixed_anchors"]) >= 3
    assert "角色姓名" in item["forbidden_elements"]


def test_normalize_scenes_accepts_empty_scene_semantics_without_rewriting():
    scenes = _normalize_scenes(
        [
            {
                "name": "办公室",
                "empty_scene_prompt": "无人纯场景，玻璃会议室，桌上放着合同。",
            }
        ],
        style_id="urban_drama",
    )

    item = scenes[0]
    assert item["empty_scene_prompt"] == "无人纯场景，玻璃会议室，桌上放着合同。"
    assert item["empty_scene_prompt_needs_synthesis"] is False


def test_normalize_scenes_rejects_empty_prompts_that_still_contain_people():
    scenes = _normalize_scenes(
        [
            {"name": "办公室", "empty_scene_prompt": "empty office, 林晓站在桌边，桌上放着合同。"},
            {"name": "客厅", "empty_scene_prompt": "无人纯场景，角色坐在沙发上，手持手机。"},
            {"name": "前厅", "empty_scene_prompt": "empty office with a woman walking to the desk"},
            {"name": "会议室", "empty_scene_prompt": "无人纯场景，林晓走进会议室，翻看合同。"},
        ],
        style_id="urban_drama",
    )

    assert [item["empty_scene_prompt_needs_synthesis"] for item in scenes] == [True, True, True, True]


def test_normalize_props_marks_missing_prompt_labels_for_synthesis_without_fallback():
    props = _normalize_props(
        [
            {
                "name": "合同",
                "visual_features": "A4纸张，右下角有签字栏",
                "plot_function": "推动谈判反转",
                "state_timeline": ["初始状态：平整放在桌面", "签署状态：右下角出现签名"],
            }
        ],
        style_id="urban_drama",
    )

    item = props[0]
    assert item["prop_prompt"] == ""
    assert item["prop_prompt_needs_synthesis"] is True
    assert item["two_d_image_prompt"] == ""
    assert item["three_d_image_prompt"] == ""
    assert item["realistic_image_prompt"] == ""
    assert item["state_timeline"] == [
        {"step_index": 1, "state": "初始状态：平整放在桌面", "description": "初始状态：平整放在桌面"},
        {"step_index": 2, "state": "签署状态：右下角出现签名", "description": "签署状态：右下角出现签名"},
    ]


def test_normalize_props_preserves_complete_prompt_labels_without_white_background_injection():
    prompt = (
        "【标准名称】：合同"
        "【原文出处 & 详细描述】：A4纸张，右下角有签字栏"
        "【2D 动漫风绘图提示词】：合同平面插画，签字栏清楚"
        "【3D 动漫风绘图提示词】：合同纸张建模，纸面厚度轻薄"
        "【写实漫剧风绘图提示词】：写实合同特写，签字栏位于右下角"
    )
    props = _normalize_props(
        [
            {
                "name": "合同",
                "prop_prompt": prompt,
            }
        ],
        style_id="urban_drama",
    )

    item = props[0]
    assert item["prop_prompt"] == prompt
    assert item["prop_prompt_needs_synthesis"] is False
    assert "纯白背景" not in item["prop_prompt"]
    assert item["two_d_image_prompt"] == "合同平面插画，签字栏清楚"
    assert item["three_d_image_prompt"] == "合同纸张建模，纸面厚度轻薄"
    assert item["realistic_image_prompt"] == "写实合同特写，签字栏位于右下角"


def test_normalize_props_requires_non_empty_extractable_prompt_label_sections():
    props = _normalize_props(
        [
            {
                "name": "合同",
                "prop_prompt": (
                    "【2D 动漫风绘图提示词】合同平面插画"
                    "【3D 动漫风绘图提示词】：合同纸张建模"
                    "【写实漫剧风绘图提示词】：写实合同特写"
                ),
            },
            {
                "name": "印章",
                "prop_prompt": (
                    "【2D 动漫风绘图提示词】："
                    "【3D 动漫风绘图提示词】：印章三维模型"
                    "【写实漫剧风绘图提示词】：写实印章特写"
                ),
            },
            {
                "name": "钥匙",
                "prop_prompt": (
                    "【2D 动漫风绘图提示词】：\n\t　"
                    "【3D 动漫风绘图提示词】：钥匙三维模型"
                    "【写实漫剧风绘图提示词】：写实钥匙特写"
                ),
            },
        ],
        style_id="urban_drama",
    )

    assert [item["prop_prompt_needs_synthesis"] for item in props] == [True, True, True]
    assert props[0]["two_d_image_prompt"] == ""
    assert props[1]["two_d_image_prompt"] == ""
    assert props[2]["two_d_image_prompt"] == ""


def test_normalizers_legacy_mode_rewrites_prompts_without_synthesis_flags(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "prompt_engine_mode", "legacy")

    character = _normalize_characters([{"name": "林晓", "description": "职场新人"}], style_id="urban_drama")[0]
    scene = _normalize_scenes([{"name": "办公室"}], style_id="urban_drama")[0]
    prop = _normalize_props([{"name": "合同", "visual_features": "A4纸张"}], style_id="urban_drama")[0]

    assert "front_prompt_needs_synthesis" not in character
    assert "turnaround_prompt_needs_synthesis" not in character
    assert "正面站立全身" in character["front_image_prompt"]
    assert "三视图" in character["turnaround_prompt"]
    assert "empty_scene_prompt_needs_synthesis" not in scene
    assert scene["empty_scene_prompt"].startswith("不能出现其他人，无人，纯场景，")
    assert "prop_prompt_needs_synthesis" not in prop
    assert "【2D 动漫风绘图提示词】" in prop["prop_prompt"]
    assert "纯白背景" in prop["prop_prompt"]
