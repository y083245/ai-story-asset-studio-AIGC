from __future__ import annotations

import re

from app.config import settings
from app.modules.template_style.style_master import load_style_master
from app.modules.workflow.prompt_composer import (
    compose_character_front,
    compose_character_turnaround,
    compose_prop_product,
    compose_scene_empty,
)


def test_compose_character_front_uses_style_master_language_and_character_fields():
    style = load_style_master("cinematic_realistic")
    prompt = compose_character_front(
        {
            "name": "苏晚晴",
            "age": "28岁",
            "gender": "女性",
            "height": "168cm",
            "body_type": "高挑匀称",
            "facial_features": "鹅蛋脸，柳叶眉，丹凤眼",
            "hair_color": "深棕色",
            "hair_style": "长直发",
            "eyes": "自然棕色",
            "skin_tone": "白皙",
            "identity": "都市商战女主",
            "personality": "冷静克制",
            "default_outfit": "米白色羊毛大衣",
            "outfit_details": "浅蓝色棉质衬衫与深灰A字裙",
            "shoes": "黑色细跟短靴",
            "accessories": "银色小耳钉",
            "core_prop": "黑色文件夹",
        },
        style,
    )

    assert len(prompt) > 200
    assert "苏晚晴" in prompt
    assert "正面站立全身角色资产图" in prompt
    assert "服装版型准确" in prompt
    assert "米白色羊毛大衣" in prompt
    assert "黑色细跟短靴" in prompt
    assert "(shallow depth of field)" in prompt
    assert "(cinematic lighting)" in prompt
    assert "(photorealistic material texture)" in prompt
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_character_front_uses_complete_fallbacks_for_missing_fields():
    style = load_style_master("chinese_ancient")
    prompt = compose_character_front({"name": "沈清辞"}, style)

    assert len(prompt) > 200
    assert "沈清辞" in prompt
    assert "符合角色身份" in prompt
    assert "中国古风" in prompt
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_character_turnaround_includes_character_bible_without_placeholders():
    style = load_style_master("xianxia")
    prompt = compose_character_turnaround(
        {
            "name": "云澈",
            "gender": "男性",
            "age": "22岁",
            "default_outfit": "玄色法袍",
            "accessories": "玉佩",
        },
        style,
    )

    assert len(prompt) > 200
    assert "云澈" in prompt
    assert "玄色法袍" in prompt
    assert "正面全身站姿" in prompt
    assert "(orthographic reference sheet)" in prompt
    assert "(shallow depth of field)" not in prompt
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_character_turnaround_uses_fallbacks_for_missing_fields():
    style = load_style_master("cinematic_realistic")
    prompt = compose_character_turnaround({"name": "陆沉"}, style)

    assert len(prompt) > 200
    assert "陆沉" in prompt
    assert "符合角色身份" in prompt
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_scene_empty_uses_scene_template_and_no_human_constraints():
    style = load_style_master("cyberpunk")
    prompt = compose_scene_empty(
        {
            "name": "霓虹雨巷",
            "scene_type": "室外街巷",
            "time_of_day": "深夜",
            "weather": "雨后",
            "lighting": "粉蓝霓虹反射",
            "mood": "潮湿压抑",
            "foreground_elements": ["积水路面", "破损广告牌"],
            "midground_elements": ["自动售卖机"],
            "background_elements": ["高楼投影屏"],
            "fixed_anchors": ["湿润柏油路", "霓虹灯牌", "狭窄街巷"],
        },
        style,
    )

    assert len(prompt) > 200
    assert prompt.startswith("不能出现其他人，无人，纯场景")
    assert "霓虹雨巷" in prompt
    assert "横向16:9" in prompt
    assert "场景设定图" in prompt
    assert "环境类型为" in prompt
    assert "核心材质" in prompt
    assert prompt.count("no humans,empty,landscape only") == 1
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_scene_empty_uses_fallbacks_for_missing_fields():
    style = load_style_master("chinese_ancient")
    prompt = compose_scene_empty({"name": "临水茶楼"}, style)

    assert len(prompt) > 200
    assert prompt.startswith("不能出现其他人，无人，纯场景")
    assert "临水茶楼" in prompt
    assert "符合场景设定" in prompt
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_prop_product_uses_prop_template_and_style_keywords():
    style = load_style_master("sci_fi")
    prompt = compose_prop_product(
        {
            "name": "量子密钥",
            "aliases": ["银色芯片", "密钥"],
            "plot_function": "开启轨道电梯权限",
            "material": "钛合金与透明晶体",
            "color": "银白色",
            "visual_features": "六边形薄片，边缘有蓝色光带",
            "size": "掌心大小",
            "state_timeline": [{"state": "待机状态", "description": "蓝光缓慢呼吸"}],
        },
        style,
    )

    assert len(prompt) > 200
    assert "量子密钥" in prompt
    assert "单一道具资产图" in prompt
    assert "主体居中完整展示" in prompt
    assert "钛合金与透明晶体" in prompt
    assert "蓝色光带" in prompt
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_prop_product_uses_fallbacks_for_missing_fields():
    style = load_style_master("urban_drama")
    prompt = compose_prop_product({"name": "旧怀表"}, style)

    assert len(prompt) > 200
    assert "旧怀表" in prompt
    assert "符合剧情功能" in prompt
    assert "真人电影级" in prompt
    assert _contains_at_least(style.visual_keywords, prompt, minimum=5)
    assert "{" not in prompt and "}" not in prompt


def test_compose_character_front_disabled_bilingual_flag_omits_keywords(monkeypatch):
    monkeypatch.setattr(settings, "bilingual_keywords_enabled", False)
    style = load_style_master("cinematic_realistic")

    prompt = compose_character_front({"name": "苏晚晴"}, style)

    assert "(shallow depth of field)" not in prompt
    assert "(cinematic lighting)" not in prompt
    assert "(photorealistic material texture)" not in prompt
    assert "双语视觉术语" not in prompt


def _contains_at_least(values: list[str], text: str, *, minimum: int) -> bool:
    pattern = "|".join(re.escape(value) for value in values)
    return len(set(re.findall(pattern, text))) >= minimum
