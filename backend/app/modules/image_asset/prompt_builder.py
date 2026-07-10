"""Prompt assembly for image generation."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.modules.image_asset.turnaround_template import (
    character_description_from_entity,
    is_strict_turnaround_prompt,
    normalize_turnaround_prompt,
    render_turnaround_template,
)
from app.modules.template_style.style_alias import normalize_style_id, normalize_style_id_for_family
from app.modules.template_style.style_master import get_negative_prompt as _style_master_negative_prompt
from app.modules.template_style.style_master import load_style_master
from app.modules.workflow.prompt_composer import (
    compose_character_front,
    compose_character_turnaround,
    compose_prop_product,
    compose_scene_empty,
)


def build_character_image_prompt(
    character: Any,
    story_bible: dict[str, Any] | None = None,
    image_type: str = "character_front",
    extra_constraints: str | None = None,
) -> tuple[str, str]:
    """Build prompt for character reference images."""
    if settings.prompt_engine_mode == "legacy":
        return _legacy_build_character_image_prompt(character, story_bible, image_type, extra_constraints)

    category_marker = "三视图" if image_type == "character_turnaround" else "正面全身"
    style_id = _style_id_from_plan(character, category_marker) or _style_id_from_bible(story_bible) or _style_id_from_entity(
        character
    )
    style = load_style_master(style_id)

    if image_type == "character_bible_sheet":
        prompt = _compose_character_bible_sheet(character, style_id)
    elif image_type == "character_turnaround":
        prompt = _find_plan_prompt(character, "三视图") or compose_character_turnaround(_character_to_dict(character), style)
    elif image_type == "character_expression":
        prompt = _find_plan_prompt(character, "表情") or _compose_character_expression(character, style_id)
    else:
        prompt = _find_plan_prompt(character, "正面全身") or compose_character_front(_character_to_dict(character), style)

    return _append_extra_constraints(prompt, extra_constraints), build_negative_prompt(style_id, image_type)


def build_scene_empty_prompt(
    scene: Any,
    story_bible: dict[str, Any] | None = None,
    extra_constraints: str | None = None,
    *,
    image_type: str = "scene_empty",
) -> tuple[str, str]:
    """Build prompt for empty scene assets."""
    if settings.prompt_engine_mode == "legacy":
        return _legacy_build_scene_empty_prompt(
            scene,
            story_bible,
            image_type=image_type,
            extra_constraints=extra_constraints,
        )

    style_id = _style_id_from_bible(story_bible) or _style_id_from_entity(scene)
    style = load_style_master(style_id)
    if image_type == "scene_with_atmosphere":
        prompt = _compose_scene_with_atmosphere(scene, style_id)
    else:
        prompt = _entity_text(scene, "empty_scene_prompt") or _with_style_name(
            compose_scene_empty(_scene_to_dict(scene), style),
            style.style_name,
        )
    return _append_extra_constraints(prompt, extra_constraints), build_negative_prompt(style_id, image_type)


def build_prop_image_prompt(
    prop: Any,
    story_bible: dict[str, Any] | None = None,
    character: Any | None = None,
    image_type: str = "prop_product",
    extra_constraints: str | None = None,
) -> tuple[str, str]:
    """Build prompt for prop images."""
    if settings.prompt_engine_mode == "legacy":
        return _legacy_build_prop_image_prompt(prop, story_bible, character, image_type, extra_constraints)

    style_id = _style_id_from_bible(story_bible) or _style_id_from_entity(prop)
    style = load_style_master(style_id)

    if image_type == "prop_usage":
        prompt = _entity_text(prop, "usage_prompt") or _compose_prop_usage(prop, character, style_id)
    else:
        prompt = _entity_text(prop, "prop_prompt") or compose_prop_product(_prop_to_dict(prop), style)

    return _append_extra_constraints(prompt, extra_constraints), build_negative_prompt(style_id, image_type)


def build_negative_prompt(style_id: str, asset_type: str) -> str:
    """Build staged negative prompt from style-master universal, style, and asset rules."""
    return _style_master_negative_prompt(style_id, asset_type)


def _find_plan_prompt(character: Any, category_marker: str) -> str:
    for item in _reference_image_plan(character):
        category = str(item.get("category") or "")
        description = str(item.get("description") or "").strip()
        if category_marker in category and description:
            return description
    return ""


def _style_id_from_plan(character: Any, category_marker: str = "") -> str:
    for item in _reference_image_plan(character):
        if category_marker and category_marker not in str(item.get("category") or ""):
            continue
        style_id = str(item.get("style_id") or "").strip()
        if style_id:
            return normalize_style_id(style_id)
    return ""


def _reference_image_plan(character: Any) -> list[dict[str, Any]]:
    plan = getattr(character, "reference_image_plan", None)
    if not isinstance(plan, list):
        return []
    return [item for item in plan if isinstance(item, dict)]


def _style_id_from_bible(story_bible: dict[str, Any] | None) -> str:
    if not isinstance(story_bible, dict):
        return ""
    style_family = str(story_bible.get("style_family") or "").strip()
    for key in ("style_id", "recommended_style_id", "style", "visual_style", "recommended_visual_style", "genre"):
        value = str(story_bible.get(key) or "").strip()
        if value:
            return normalize_style_id_for_family(value, style_family)
    return ""


def _style_id_from_entity(entity: Any) -> str:
    for attr in ("style_id", "style"):
        value = _entity_text(entity, attr)
        if value:
            return normalize_style_id(value)
    return "cinematic_realistic"


def _character_to_dict(character: Any) -> dict[str, Any]:
    description = _entity_text(character, "description") or _entity_text(character, "personality")
    role = _entity_text(character, "role_type") or _entity_text(character, "role") or _entity_text(character, "identity")
    return {
        "name": _entity_text(character, "name", "未命名角色"),
        "age": _entity_text(character, "age") or _entity_text(character, "age_range"),
        "gender": _entity_text(character, "gender"),
        "height": _entity_text(character, "height"),
        "body_type": _entity_text(character, "body_type"),
        "face_shape": _entity_text(character, "face_shape"),
        "facial_features": _entity_text(character, "facial_bone_structure")
        or _entity_text(character, "facial_features"),
        "hair_color": _entity_text(character, "hair_color"),
        "hair_style": _entity_text(character, "hair_style"),
        "eyes": _entity_text(character, "eyes"),
        "eye_color": _entity_text(character, "eye_color") or _entity_text(character, "eyes"),
        "skin_tone": _entity_text(character, "skin_tone"),
        "identity": _entity_text(character, "identity") or role,
        "role": role,
        "story_role": role,
        "personality": description,
        "description": description,
        "default_outfit": _entity_text(character, "default_outfit") or _entity_text(character, "outfit"),
        "upper_clothing": _entity_text(character, "upper_clothing") or _entity_text(character, "default_outfit"),
        "lower_clothing": _entity_text(character, "lower_clothing") or _entity_text(character, "outfit_details"),
        "outfit_details": _entity_text(character, "outfit_details"),
        "shoes": _entity_text(character, "shoes"),
        "accessories": _entity_text(character, "accessories"),
        "core_prop": _entity_text(character, "core_prop") or _entity_text(character, "accessories"),
    }


def _scene_to_dict(scene: Any) -> dict[str, Any]:
    return {
        "scene_name": _entity_text(scene, "scene_name") or _entity_text(scene, "name", "未命名场景"),
        "name": _entity_text(scene, "scene_name") or _entity_text(scene, "name", "未命名场景"),
        "scene_type": _entity_text(scene, "scene_type") or _entity_text(scene, "type"),
        "environment_type": _entity_text(scene, "environment_type") or _entity_text(scene, "scene_type"),
        "description": _entity_text(scene, "description"),
        "time_of_day": _entity_text(scene, "time_of_day"),
        "weather": _entity_text(scene, "weather"),
        "lighting": _entity_text(scene, "lighting"),
        "mood": _entity_text(scene, "mood"),
        "fixed_anchors": _entity_list(scene, "fixed_anchors"),
        "foreground_elements": _entity_list(scene, "foreground_elements"),
        "midground_elements": _entity_list(scene, "midground_elements"),
        "background_elements": _entity_list(scene, "background_elements"),
    }


def _prop_to_dict(prop: Any) -> dict[str, Any]:
    return {
        "name": _entity_text(prop, "name", "未命名道具"),
        "prop_name": _entity_text(prop, "name", "未命名道具"),
        "aliases": _entity_list(prop, "aliases"),
        "visual_features": _entity_text(prop, "visual_features") or _entity_text(prop, "description"),
        "description": _entity_text(prop, "description") or _entity_text(prop, "visual_features"),
        "material": _entity_text(prop, "material"),
        "color": _entity_text(prop, "color"),
        "size": _entity_text(prop, "size"),
        "plot_function": _entity_text(prop, "plot_function") or _entity_text(prop, "function"),
        "state_timeline": getattr(prop, "state_timeline", None) or [],
    }


def _compose_character_expression(character: Any, style_id: str) -> str:
    style = load_style_master(style_id)
    data = _character_to_dict(character)
    base = compose_character_front(data, style).rstrip("。")
    return f"{base}，表情集参考，包含平静、警觉、悲伤、坚定等多种情绪变化，服装和五官保持一致。"


def _compose_character_bible_sheet(character: Any, style_id: str) -> str:
    data = _character_to_dict(character)
    base = compose_character_front(data, load_style_master(style_id)).rstrip("。")
    name = data["name"]
    return (
        f"纯白背景，角色设定板，{name}正面站姿全身，右侧标注服装版型细节，"
        "下方展示关键配饰，头发正面/侧面发缝、袖长、下装、鞋型、配饰清晰可辨，"
        "白底无阴影，整个图片适合后续作为角色一致性的视觉锚定参考图，高清商业棚拍光，"
        f"真实布料纤维纹理，不裁切。{base}。"
    )


def _compose_scene_with_atmosphere(scene: Any, style_id: str) -> str:
    base = _entity_text(scene, "scene_prompt") or _entity_text(scene, "empty_scene_prompt")
    if not base:
        base = compose_scene_empty(_scene_to_dict(scene), load_style_master(style_id))
    scene_name = _entity_text(scene, "scene_name") or _entity_text(scene, "name", "场景")
    atmosphere = _join_nonempty([_entity_text(scene, "mood"), _entity_text(scene, "lighting")])
    atmosphere = atmosphere or "保持空间结构一致，强化氛围光和环境质感"
    return (
        f"以参考空场景为唯一空间锚点，生成同一地点的氛围版资产图，场景名称：{scene_name}，"
        f"{base.rstrip('。')}，{atmosphere}，固定锚点、空间布局、主要物件位置与参考图保持一致，"
        "无人纯场景，不出现角色，不出现文字、水印或logo。"
    )


def _compose_prop_usage(prop: Any, character: Any | None, style_id: str) -> str:
    base = compose_prop_product(_prop_to_dict(prop), load_style_master(style_id)).rstrip("。")
    if character is None:
        return f"{base}，展示道具在剧情场景中的自然使用状态。"
    return f"{base}，{_entity_text(character, 'name', '角色')}正在自然使用该道具，动作符合剧情功能。"


def _append_extra_constraints(prompt: str, extra_constraints: str | None) -> str:
    extra = str(extra_constraints or "").strip()
    return f"{prompt} {extra}" if extra else prompt


def _with_style_name(prompt: str, style_name: str) -> str:
    return prompt if style_name in prompt else f"{style_name}，{prompt}"


def _entity_text(entity: Any, attr: str, default: str = "") -> str:
    value = getattr(entity, attr, default)
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (int, float)):
        return str(value)
    return default


def _entity_list(entity: Any, attr: str) -> list[str]:
    value = getattr(entity, attr, None)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _legacy_build_character_image_prompt(
    character: Any,
    story_bible: dict[str, Any] | None = None,
    image_type: str = "character_front",
    extra_constraints: str | None = None,
) -> tuple[str, str]:
    name = getattr(character, "name", "character")
    gender = getattr(character, "gender", None) or ""
    age = getattr(character, "age", None) or ""
    body_type = getattr(character, "body_type", None) or ""
    height = getattr(character, "height", None) or ""
    face_shape = getattr(character, "face_shape", None) or ""
    facial_features = getattr(character, "facial_bone_structure", None) or getattr(character, "facial_features", None) or ""
    hair_color = getattr(character, "hair_color", None) or ""
    hair_style = getattr(character, "hair_style", None) or ""
    eyes = getattr(character, "eyes", None) or ""
    eyebrows = getattr(character, "eyebrows", None) or ""
    nose = getattr(character, "nose", None) or ""
    mouth = getattr(character, "mouth", None) or ""
    skin_tone = getattr(character, "skin_tone", None) or ""
    outfit = getattr(character, "default_outfit", None) or ""
    outfit_details = getattr(character, "outfit_details", None) or ""
    shoes = getattr(character, "shoes", None) or ""
    accessories = getattr(character, "accessories", None) or ""
    identity = getattr(character, "identity", None) or ""
    personality = getattr(character, "personality", None) or ""
    description = getattr(character, "description", None) or ""
    consistency_tag = getattr(character, "consistency_tag", None) or ""

    if image_type == "character_bible_sheet":
        prompt = _compose_character_bible_sheet(character, "cinematic_realistic")
        return _append_extra_constraints(prompt, extra_constraints), _legacy_build_character_negative(image_type)

    if image_type == "character_turnaround":
        prompt = _legacy_turnaround_prompt_from_plan(character)
        if not prompt:
            prompt = render_turnaround_template(character_description_from_entity(character))
        return _append_extra_constraints(prompt, extra_constraints), _legacy_build_character_negative(image_type)

    if image_type == "character_front":
        prompt = _legacy_front_prompt_from_plan(character)
        if prompt:
            return _append_extra_constraints(prompt, extra_constraints), _legacy_build_character_negative(image_type)

    parts: list[str] = []
    if image_type == "character_front":
        parts.append("全部为正面站立全身图片")
        parts.append("图片人物背景为纯白")
        parts.append("纯白背景")
        parts.append(f"角色名称：{name}")
    elif image_type == "character_expression":
        parts.append("表情集，包含多种表情变化")
        parts.append(f"角色名称：{name}")

    if gender:
        parts.append(f"性别：{gender}")
    if age:
        parts.append(f"年龄：{age}")
    if height:
        parts.append(f"身高：{height}")
    if body_type:
        parts.append(f"体型：{body_type}")
    face_text = _join_nonempty([face_shape, facial_features, eyebrows, nose, mouth])
    if face_text:
        parts.append(f"脸部特征：{face_text}")
    if hair_color:
        parts.append(f"发色：{hair_color}")
    if hair_style:
        parts.append(f"发型：{hair_style}")
    if eyes:
        parts.append(f"眼睛颜色：{eyes}")
    if skin_tone:
        parts.append(f"肤色：{skin_tone}")
    if identity:
        parts.append(f"身份：{identity}")
    if personality:
        parts.append(f"人物性格：{personality}")
    if description and description not in {identity, personality}:
        parts.append(f"形象描述：{description}")
    if outfit:
        parts.append(f"上身服装：{outfit}")
    if outfit_details:
        parts.append(f"下身服装：{outfit_details}")
    if shoes:
        parts.append(f"鞋子：{shoes}")
    if accessories:
        parts.append(f"配饰：{accessories}")
    if consistency_tag:
        parts.append(f"一致性要求：{consistency_tag}")
    style = _legacy_extract_style_from_bible(story_bible)
    if style:
        parts.append(style.rstrip("，"))
    prompt = "，".join(parts) + "。"
    return _append_extra_constraints(prompt, extra_constraints), _legacy_build_character_negative(image_type)


def _legacy_turnaround_prompt_from_plan(character: Any) -> str:
    for item in _reference_image_plan(character):
        category = str(item.get("category") or "")
        description = str(item.get("description") or "").strip()
        style_id = str(item.get("style_id") or "").strip()
        if "三视图" not in category or not _legacy_is_strict_turnaround_template(description, style_id=style_id or None):
            continue
        if style_id:
            return normalize_turnaround_prompt(
                description,
                character_description_from_entity(character),
                style_id=style_id,
            )
        return description
    return ""


def _legacy_front_prompt_from_plan(character: Any) -> str:
    for item in _reference_image_plan(character):
        category = str(item.get("category") or "")
        description = str(item.get("description") or "").strip()
        if "正面全身" in category and description:
            return description
    return ""


def _legacy_is_strict_turnaround_template(description: str, *, style_id: str | None = None) -> bool:
    if style_id:
        return is_strict_turnaround_prompt(description, style_id=style_id)
    return is_strict_turnaround_prompt(description)


def _legacy_build_scene_empty_prompt(
    scene: Any,
    story_bible: dict[str, Any] | None = None,
    image_type: str = "scene_empty",
    extra_constraints: str | None = None,
) -> tuple[str, str]:
    scene_name = getattr(scene, "scene_name", "scene")
    scene_type = getattr(scene, "scene_type", None) or "室内"
    time_of_day = getattr(scene, "time_of_day", None) or ""
    weather = getattr(scene, "weather", None) or ""
    lighting = getattr(scene, "lighting", None) or ""
    mood = getattr(scene, "mood", None) or ""
    fixed_anchors = getattr(scene, "fixed_anchors", None) or []
    foreground = getattr(scene, "foreground_elements", None) or []
    midground = getattr(scene, "midground_elements", None) or []
    background = getattr(scene, "background_elements", None) or []
    empty_scene_prompt = getattr(scene, "empty_scene_prompt", None)

    if image_type == "scene_with_atmosphere":
        prompt_parts = [
            "以参考空场景为唯一空间锚点，生成同一地点的氛围版资产图",
            f"场景名称：{scene_name}",
            f"场景类型：{scene_type}",
            "固定锚点、空间布局、主要物件位置与参考图保持一致",
            "无人纯场景",
        ]
        if empty_scene_prompt:
            prompt_parts.append(empty_scene_prompt)
    else:
        prompt_parts = [empty_scene_prompt] if empty_scene_prompt else [
            "不能出现其他人，无人纯场景",
            f"场景名称：{scene_name}",
            f"场景类型：{scene_type}",
        ]
    if time_of_day:
        prompt_parts.append(f"时段：{time_of_day}")
    if weather:
        prompt_parts.append(f"天气：{weather}")
    if lighting:
        prompt_parts.append(f"光照：{lighting}")
    if mood:
        prompt_parts.append(f"氛围：{mood}")
    if fixed_anchors:
        prompt_parts.append(f"必须包含的固定锚点：{'、'.join(fixed_anchors[:5])}")
    else:
        prompt_parts.append("必须包含的固定锚点：核心场景结构和布局")
    if foreground:
        prompt_parts.append(f"前景元素：{'、'.join(foreground[:3])}")
    if midground:
        prompt_parts.append(f"中景元素：{'、'.join(midground[:3])}")
    if background:
        prompt_parts.append(f"背景元素：{'、'.join(background[:3])}")
    style = _legacy_extract_style_from_bible(story_bible)
    if style:
        prompt_parts.append(style.rstrip("，"))
    prompt = "，".join(prompt_parts) + "。"
    return _append_extra_constraints(prompt, extra_constraints), "人物，角色，文字，水印，logo，模糊，变形"


def _legacy_build_prop_image_prompt(
    prop: Any,
    story_bible: dict[str, Any] | None = None,
    character: Any | None = None,
    image_type: str = "prop_product",
    extra_constraints: str | None = None,
) -> tuple[str, str]:
    prop_name = _entity_text(prop, "name", "prop")
    visual_features = _entity_text(prop, "visual_features")
    material = _entity_text(prop, "material")
    color = _entity_text(prop, "color")
    size = _entity_text(prop, "size")
    plot_function = _entity_text(prop, "plot_function")
    prop_prompt = _entity_text(prop, "prop_prompt")
    usage_prompt = _entity_text(prop, "usage_prompt")

    parts: list[str] = []
    if image_type == "prop_product":
        parts.append(prop_prompt if prop_prompt else "纯白背景")
        parts.append(f"道具名称：{prop_name}")
    elif image_type == "prop_usage":
        if usage_prompt:
            parts.append(usage_prompt)
        parts.append(f"道具名称：{prop_name}")
        parts.append("道具在场景中的使用状态")
        if character:
            parts.append(f"角色{_entity_text(character, 'name', 'character')}手持或使用该道具")

    if plot_function:
        parts.append(f"剧情功能：{plot_function}")
    if visual_features:
        parts.append(f"视觉特征：{visual_features}")
    if material:
        parts.append(f"材质：{material}")
    if color:
        parts.append(f"颜色：{color}")
    if size:
        parts.append(f"尺寸：{size}")
    style = _legacy_extract_style_from_bible(story_bible)
    if style:
        parts.append(style.rstrip("，"))
    prompt = "，".join(parts) + "。"
    negative_prompt = "人物，手，场景，文字，水印，logo，阴影过重" if image_type == "prop_product" else "文字，水印，logo，模糊，变形"
    return _append_extra_constraints(prompt, extra_constraints), negative_prompt


def _legacy_extract_style_from_bible(story_bible: dict[str, Any] | None) -> str:
    if not story_bible:
        return ""
    style = story_bible.get("visual_style", "") or story_bible.get("recommended_visual_style", "")
    if style:
        return f"画面风格：{style}，"
    return ""


def _join_nonempty(values: list[Any]) -> str:
    return "，".join(str(value).strip() for value in values if str(value or "").strip())


def _legacy_build_character_negative(image_type: str) -> str:
    base = "低质量，模糊，变形，多肢，多手指，文字，水印，logo"
    extras: dict[str, str] = {
        "character_bible_sheet": "裁切，局部特写，非白底",
        "character_front": "侧面视角",
        "character_turnaround": "单一角度",
        "character_expression": "无表情",
    }
    extra = extras.get(image_type, "")
    return f"{base}，{extra}" if extra else base
