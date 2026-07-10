"""Local fallback prompt composition for staged image prompts."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.modules.template_style.style_master import StyleMasterProfile
from app.modules.workflow.normalizers.scene import SCENE_NO_HUMANS_CLAUSE, SCENE_PROMPT_PREFIX

_PLACEHOLDER_PATTERN = re.compile(r"\{(?P<name>[^{}]+)\}")
_ENGLISH_PARENTHESES_PATTERN = re.compile(r"\([A-Za-z][A-Za-z0-9 ,./-]*[A-Za-z]\)")


def compose_character_front(character: dict[str, Any], style: StyleMasterProfile) -> str:
    """Compose a complete character front prompt from the style master template."""
    values = _character_values(character)
    prompt = _render_prompt_block(style.character_prompt_template, values)
    return _enrich_prompt(
        prompt,
        style,
        values["character_name"],
        values["default_outfit"],
        values["shoes"],
        values["accessories"],
    )


def compose_character_turnaround(character: dict[str, Any], style: StyleMasterProfile) -> str:
    values = _character_values(character)
    values["character_bible"] = _character_bible(values)
    prompt = _render_prompt_block(style.character_turnaround_template, values)
    return _enrich_prompt(
        prompt,
        style,
        values["character_name"],
        values["default_outfit"],
        bilingual_profile="turnaround",
    )


def compose_scene_empty(scene: dict[str, Any], style: StyleMasterProfile) -> str:
    values = _scene_values(scene)
    prompt = _render_prompt_block(style.scene_prompt_template, values)
    if not prompt.startswith(SCENE_PROMPT_PREFIX):
        prompt = f"{SCENE_PROMPT_PREFIX}{prompt.lstrip('，, ')}"
    if SCENE_NO_HUMANS_CLAUSE not in prompt:
        prompt = prompt.rstrip("。；;，, ") + f"，{SCENE_NO_HUMANS_CLAUSE}。"
    return _enrich_prompt(prompt, style, values["scene_name"], values["materials"])


def compose_prop_product(prop: dict[str, Any], style: StyleMasterProfile) -> str:
    values = _prop_values(prop)
    prompt = _render_prompt_block(style.prop_prompt_template, values)
    return _enrich_prompt(prompt, style, values["prop_name"], values["prop_material"], values["prop_pattern"])


def _render_prompt_block(template: str, values: dict[str, str]) -> str:
    prompt = _prompt_body(template)

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        return values.get(name) or _fallback_for_placeholder(name)

    rendered = _PLACEHOLDER_PATTERN.sub(replace, prompt)
    return _clean_prompt(rendered)


def _prompt_body(template: str) -> str:
    marker = "Prompt："
    if marker not in template:
        marker = "Prompt:"
    body = template.split(marker, 1)[1] if marker in template else template
    negative_index = body.find("Negative Prompt")
    if negative_index >= 0:
        body = body[:negative_index]
    return body


def _character_values(character: dict[str, Any]) -> dict[str, str]:
    name = _value(character, "name", "未命名角色")
    upper = _first_text(
        _value(character, "upper_clothing"),
        _value(character, "default_outfit"),
        _value(character, "outfit"),
        "符合角色身份的上身服装",
    )
    lower = _first_text(
        _value(character, "lower_clothing"),
        _value(character, "outfit_details"),
        "符合角色身份的下身服装",
    )
    shoes = _first_text(_value(character, "shoes"), "符合角色身份的鞋履")
    accessories = _first_text(_value(character, "accessories"), "符合角色身份的可见配饰")
    core_prop = _first_text(_value(character, "core_prop"), _value(character, "key_prop"), accessories)
    return {
        "character_name": name,
        "asset_name": name,
        "age": _first_text(_value(character, "age"), _value(character, "age_range"), "符合角色设定的年龄"),
        "gender": _first_text(_value(character, "gender"), "符合角色设定的性别"),
        "height": _first_text(_value(character, "height"), "符合角色身份的身高比例"),
        "body_type": _first_text(_value(character, "body_type"), "符合角色身份的体型"),
        "face_features": _first_text(
            _value(character, "face_features"),
            _value(character, "facial_features"),
            _value(character, "face_shape"),
            "符合角色身份的脸部特征",
        ),
        "hair_color": _first_text(_value(character, "hair_color"), "自然发色"),
        "hair_style": _first_text(_value(character, "hair_style"), "符合角色身份的发型"),
        "eye_color": _first_text(_value(character, "eye_color"), _value(character, "eyes"), "自然"),
        "skin_texture": _first_text(_value(character, "skin_texture"), _value(character, "skin_tone"), "真实可信"),
        "story_role": _first_text(_value(character, "story_role"), _value(character, "identity"), _value(character, "role"), "故事角色"),
        "personality": _first_text(_value(character, "personality"), _value(character, "description"), "符合故事气质"),
        "upper_clothing": upper,
        "lower_clothing": lower,
        "default_outfit": f"{upper}，{lower}",
        "shoes": shoes,
        "accessories": accessories,
        "core_prop": core_prop,
        "must_keep": _first_text(_value(character, "must_keep"), f"{name}的五官、发型、服装和关键配饰"),
        "角色名": name,
        "年龄": _first_text(_value(character, "age"), _value(character, "age_range"), "符合角色设定的年龄"),
        "性别": _first_text(_value(character, "gender"), "符合角色设定的性别"),
        "身高": _first_text(_value(character, "height"), "符合角色身份的身高比例"),
        "体型": _first_text(_value(character, "body_type"), "符合角色身份的体型"),
        "脸型与五官": _first_text(
            _value(character, "face_features"),
            _value(character, "facial_features"),
            _value(character, "face_shape"),
            "符合角色身份的脸部特征",
        ),
        "发色与发型": _join_values(
            [_value(character, "hair_color"), _value(character, "hair_style")],
            "符合角色身份的发色与发型",
        ),
        "眼睛颜色与眼神": _first_text(_value(character, "eye_color"), _value(character, "eyes"), "自然眼神"),
        "性格气质": _first_text(_value(character, "personality"), _value(character, "description"), "符合故事气质"),
        "上身服装": upper,
        "下身服装": lower,
        "鞋履": shoes,
        "配饰": accessories,
    }


def _scene_values(scene: dict[str, Any]) -> dict[str, str]:
    name = _first_text(_value(scene, "scene_name"), _value(scene, "name"), "未命名场景")
    weather_light = _join_values([_value(scene, "weather"), _value(scene, "lighting")], "符合场景设定的天气与光线")
    foreground = _join_values(
        [_value(scene, "foreground"), _list_text(scene.get("foreground_elements"))],
        "符合场景设定的前景元素",
    )
    midground = _join_values(
        [_value(scene, "midground"), _list_text(scene.get("midground_elements")), _list_text(scene.get("fixed_anchors"))],
        "符合场景设定的中景核心结构",
    )
    background = _join_values(
        [_value(scene, "background"), _list_text(scene.get("background_elements"))],
        "符合场景设定的远景层次",
    )
    materials = _join_values(
        [_value(scene, "materials"), _value(scene, "core_materials"), _list_text(scene.get("fixed_anchors"))],
        "符合场景设定的核心材质",
    )
    return {
        "scene_name": name,
        "asset_name": name,
        "environment_type": _first_text(_value(scene, "environment_type"), _value(scene, "scene_type"), "符合故事设定的环境类型"),
        "time_of_day": _first_text(_value(scene, "time_of_day"), _value(scene, "time"), "符合剧情的具体时间"),
        "weather_light": weather_light,
        "mood": _first_text(_value(scene, "mood"), _value(scene, "description"), "符合故事氛围"),
        "foreground": foreground,
        "midground": midground,
        "background": background,
        "materials": materials,
        "场景名称": name,
        "环境类型": _first_text(_value(scene, "environment_type"), _value(scene, "scene_type"), "符合故事设定的环境类型"),
        "具体时间与天气": weather_light,
        "氛围": _first_text(_value(scene, "mood"), _value(scene, "description"), "符合故事氛围"),
        "前景元素": foreground,
        "中景空间主体": midground,
        "远景城市层次": background,
    }


def _prop_values(prop: dict[str, Any]) -> dict[str, str]:
    name = _first_text(_value(prop, "prop_name"), _value(prop, "name"), "未命名道具")
    aliases = _first_text(_list_text(prop.get("aliases")), "符合剧情称呼的别名")
    visual_features = _first_text(_value(prop, "visual_features"), _value(prop, "description"), f"{name}的可识别造型")
    material = _first_text(_value(prop, "prop_material"), _value(prop, "material"), "符合剧情功能的材质")
    color = _first_text(_value(prop, "prop_color"), _value(prop, "color"), "符合剧情功能的颜色")
    shape = _first_text(_value(prop, "prop_shape"), _value(prop, "shape"), visual_features)
    pattern = _first_text(_value(prop, "prop_pattern"), _value(prop, "pattern"), visual_features)
    effect = _first_text(_value(prop, "prop_effect"), _state_text(prop.get("state_timeline")), "符合剧情功能的状态")
    function = _first_text(_value(prop, "prop_function"), _value(prop, "plot_function"), _value(prop, "function"), "符合剧情功能")
    return {
        "prop_name": name,
        "asset_name": name,
        "asset_aliases": aliases,
        "prop_function": function,
        "prop_material": material,
        "prop_color": color,
        "prop_shape": shape,
        "prop_pattern": pattern,
        "prop_wear": _first_text(_value(prop, "prop_wear"), _value(prop, "wear"), "符合剧情使用痕迹"),
        "prop_effect": effect,
        "size": _first_text(_value(prop, "size"), "符合道具用途的尺寸"),
        "道具名称": name,
        "材质": material,
        "颜色": color,
        "造型": shape,
        "纹理或磨损": pattern,
        "用途": function,
    }


def _character_bible(values: dict[str, str]) -> str:
    keys = [
        "character_name",
        "age",
        "gender",
        "height",
        "body_type",
        "face_features",
        "hair_color",
        "hair_style",
        "eye_color",
        "story_role",
        "personality",
        "default_outfit",
        "shoes",
        "accessories",
        "core_prop",
    ]
    return "，".join(values[key] for key in keys if values.get(key))


def _enrich_prompt(prompt: str, style: StyleMasterProfile, *anchors: str, bilingual_profile: str = "default") -> str:
    extras = [
        f"视觉关键词：{'，'.join(style.visual_keywords[:8])}",
        style.color_light_rules,
        style.material_rules,
        style.composition_rules,
        "资产一致性要求：" + "，".join(anchor for anchor in anchors if anchor),
    ]
    bilingual_terms = _bilingual_keyword_annotations(prompt, style, bilingual_profile=bilingual_profile)
    if bilingual_terms:
        extras.append(f"双语视觉术语：{bilingual_terms}")
    enriched = prompt.rstrip("。；;，, ") + "，" + "，".join(_clean_prompt(item).rstrip("。") for item in extras if item) + "。"
    return _clean_prompt(enriched)


def _bilingual_keyword_annotations(prompt: str, style: StyleMasterProfile, *, bilingual_profile: str = "default") -> str:
    if not settings.bilingual_keywords_enabled:
        return ""
    context = "，".join(
        [
            prompt,
            "，".join(style.visual_keywords),
            style.color_light_rules,
            style.material_rules,
            style.composition_rules,
        ]
    )
    if _ENGLISH_PARENTHESES_PATTERN.search(context):
        return ""

    terms = [
        "电影级光影层次 (cinematic lighting)",
        "真实材质纹理 (photorealistic material texture)",
    ]
    if bilingual_profile == "turnaround":
        terms.insert(0, "正交参考图构图 (orthographic reference sheet)")
    elif "单一道具资产图" in prompt:
        terms.insert(0, "产品级居中构图 (centered product shot)")
    elif prompt.startswith(SCENE_PROMPT_PREFIX) or "场景设定图" in prompt:
        terms.insert(0, "广角环境构图 (wide establishing shot)")
    else:
        terms.insert(0, "85mm 浅景深 (shallow depth of field)")
    return "，".join(terms[:3])


def _fallback_for_placeholder(name: str) -> str:
    readable = name.replace("_", " ")
    return f"符合资产设定的{readable}"


def _value(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key, default)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return default


def _first_text(*values: str) -> str:
    return next((value.strip() for value in values if value.strip()), "")


def _join_values(values: list[str], fallback: str) -> str:
    joined = "，".join(value.strip() for value in values if value.strip())
    return joined or fallback


def _list_text(value: Any) -> str:
    if isinstance(value, list):
        return "，".join(str(item).strip() for item in value if str(item or "").strip())
    return str(value or "").strip()


def _state_text(value: Any) -> str:
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("description") or item.get("state") or "").strip())
            else:
                parts.append(str(item or "").strip())
        return "，".join(part for part in parts if part)
    return str(value or "").strip()


def _clean_prompt(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
