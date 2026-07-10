from __future__ import annotations

import dataclasses
import re

import pytest

from app.modules.template_style import style_master
from app.modules.template_style.style_alias import SUPPORTED_STYLE_IDS
from app.modules.template_style.style_master import (
    STYLE_DOC_ROOT_RELATIVE,
    STYLE_MASTER_DOCS,
    StyleMasterProfile,
    _resolve_docs_root,
    get_negative_prompt,
    load_style_master,
)

EXPECTED_FIELDS = [
    "style_id",
    "style_name",
    "visual_keywords",
    "color_light_rules",
    "material_rules",
    "composition_rules",
    "style_taboos",
    "negative_prompt_universal",
    "negative_prompt_style_specific",
    "character_prompt_template",
    "character_expression_template",
    "character_turnaround_template",
    "scene_prompt_template",
    "prop_prompt_template",
    "character_example",
    "scene_example",
    "prop_example",
]


@pytest.mark.parametrize(
    ("style_id", "style_name"),
    [
        ("urban_drama", "都市剧情类真人写实风"),
        ("xianxia", "古风仙侠类"),
        ("cyberpunk", "赛博朋克类"),
        ("sci_fi", "未来科幻电影类"),
        ("cinematic_realistic", "真人电影级"),
        ("chinese_ancient", "中国古风"),
        ("urban_drama_3d_anime", "3D都市剧情类动漫风"),
        ("chinese_historical_3d_anime", "中国古风_3D动漫版"),
        ("xianxia_3d_anime", "古风仙侠类_3D动漫版"),
        ("future_scifi_movie_3d_anime", "未来科幻电影类_3D动漫版"),
        ("cinematic_live_action_3d_anime", "真人电影级_3D动漫版"),
        ("cyberpunk_3d_anime", "赛博朋克类_3D动漫版"),
    ],
)
def test_load_style_master_loads_each_supported_style_with_non_empty_fields(style_id: str, style_name: str):
    profile = load_style_master(style_id)

    assert isinstance(profile, StyleMasterProfile)
    assert profile.style_id == style_id
    assert profile.style_name == style_name
    assert [field.name for field in dataclasses.fields(StyleMasterProfile)] == EXPECTED_FIELDS
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.style_name = "changed"  # type: ignore[misc]

    for field in dataclasses.fields(profile):
        value = getattr(profile, field.name)
        if isinstance(value, list):
            assert value
            assert all(item.strip() for item in value)
        else:
            assert value.strip()


def test_load_style_master_normalizes_live_action_alias_to_cinematic_realistic():
    canonical = load_style_master("cinematic_realistic")
    alias = load_style_master("live_action_cinematic")

    assert alias == canonical


def test_all_supported_styles_have_existing_style_master_docs():
    docs_root = _resolve_docs_root()
    assert set(STYLE_MASTER_DOCS) == set(SUPPORTED_STYLE_IDS)

    missing = [filename for _, filename in STYLE_MASTER_DOCS.values() if not (docs_root / filename).is_file()]

    assert docs_root.name == STYLE_DOC_ROOT_RELATIVE.name
    assert missing == []


@pytest.mark.parametrize(
    "style_id",
    [
        "urban_drama_3d_anime",
        "chinese_historical_3d_anime",
        "xianxia_3d_anime",
        "future_scifi_movie_3d_anime",
        "cinematic_live_action_3d_anime",
        "cyberpunk_3d_anime",
    ],
)
def test_3d_anime_style_master_and_negatives_load_without_realistic_fallback(style_id: str):
    profile = load_style_master(style_id)
    negative = get_negative_prompt(style_id, "character_front")

    assert profile.style_id == style_id
    assert profile.style_name
    assert "3D" in profile.style_name
    assert "动漫" in profile.style_name
    assert negative


def test_get_negative_prompt_uses_master_universal_style_and_asset_specific_terms():
    negative_prompt = get_negative_prompt("live_action_cinematic", "scene")

    assert "低清晰度" in negative_prompt
    assert "二次元" in negative_prompt
    assert "人物" in negative_prompt
    assert "人影" in negative_prompt
    assert "角色姓名" in negative_prompt
    assert len(negative_prompt) > 200
    assert negative_prompt not in {
        "人物，角色，文字，水印，logo，模糊，变形",
        "人物，手，场景，文字，水印，logo，阴影过重",
        "文字，水印，logo，模糊，变形",
    }


def test_get_negative_prompt_does_not_leak_positive_template_sections():
    negative_prompt = get_negative_prompt("live_action_cinematic", "character")

    assert "角色半身情绪图模板" not in negative_prompt
    assert "Prompt" not in negative_prompt
    assert "{character_name}" not in negative_prompt
    assert "{expression}" not in negative_prompt
    assert "表情{" not in negative_prompt


@pytest.mark.parametrize(
    ("asset_type", "expected_term"),
    [
        ("character_front", "动漫脸"),
        ("front", "动漫脸"),
        ("bible_sheet", "动漫脸"),
        ("character_bible_sheet", "动漫脸"),
        ("prop_product", "多余道具"),
        ("product", "多余道具"),
    ],
)
def test_get_negative_prompt_supports_common_asset_type_aliases(asset_type: str, expected_term: str):
    negative_prompt = get_negative_prompt("live_action_cinematic", asset_type)

    assert expected_term in negative_prompt


def test_get_negative_prompt_deduplicates_terms_across_universal_style_and_asset_specific_parts():
    negative_prompt = get_negative_prompt("live_action_cinematic", "scene")
    terms = _split_negative_terms(negative_prompt)

    for repeated_term in ("低清晰度", "人群", "文字", "水印", "logo", "UI界面"):
        assert terms.count(repeated_term) == 1


def test_load_style_master_reads_complete_negative_library_not_role_template_labels(monkeypatch):
    style_master.load_style_master.cache_clear()
    style_master.get_negative_prompt.cache_clear()
    monkeypatch.setattr(style_master, "_read_style_doc", lambda filename: _synthetic_style_doc_with_late_role_negative())

    profile = load_style_master("cinematic_realistic")

    assert profile.negative_prompt_universal == "低清晰度，模糊，水印，logo"
    assert profile.negative_prompt_style_specific == "完整专属词，风格跑偏"
    assert "动漫脸" not in profile.negative_prompt_universal
    assert "CG塑料感" not in profile.negative_prompt_universal

    style_master.load_style_master.cache_clear()
    style_master.get_negative_prompt.cache_clear()


def _split_negative_terms(prompt: str) -> list[str]:
    return [term for term in (item.strip() for item in re.split(r"[，,、；;。]", prompt)) if term]


def _synthetic_style_doc_with_late_role_negative() -> str:
    return """
Story Asset Studio 高质量风格包提示词模板
风格名称：真人电影级
风格 ID：live_action_cinematic

【视觉关键词】
真实，电影

【色彩与光影规则】
完整色彩规则

【材质与细节规则】
完整材质规则

【镜头与构图规则】
完整构图规则

【本风格禁忌】
禁忌一，禁忌二

============================================================
十、完整负面提示词库
============================================================
【通用负面提示词】
低清晰度，模糊，水印，logo

【本风格专属负面词】
完整专属词，风格跑偏

============================================================
三、角色生图 Prompt 模板
============================================================
Prompt：
角色模板正文

Negative Prompt：
【通用负面提示词】
低质，动漫脸，CG塑料感

【角色半身情绪图模板】
角色半身模板正文

============================================================
四、角色三视图 / 建模设定板 Prompt 模板
============================================================
Prompt：
角色三视图模板正文

Negative Prompt：
三视图错误

============================================================
六、场景生图 Prompt 模板
============================================================
Prompt：
场景模板正文

Negative Prompt：
人物，水印

============================================================
八、道具生图 Prompt 模板
============================================================
Prompt：
道具模板正文

Negative Prompt：
人物，logo

============================================================
十一、可直接复制的示例 Prompt
============================================================
【角色示例】
角色示例正文

【场景示例】
场景示例正文

【道具示例】
道具示例正文
"""
