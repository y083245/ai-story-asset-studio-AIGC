"""Scene prompt builder for the Scene Library module.

Generates two prompts for each scene:
1. scene_prompt: A detailed visual description of the scene (NO character names).
2. empty_scene_prompt: An empty-scene prompt starting with
   "不能出现其他人，无人纯场景，" for image generation.

Hard rules:
- scene_prompt MUST NOT contain any character names.
- empty_scene_prompt MUST start with "不能出现其他人，无人纯场景，".
- empty_scene_prompt MUST include "no humans, empty scene, landscape only".
"""

from __future__ import annotations

from typing import Any

from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest

# ---------------------------------------------------------------------------
# Deterministic prompt builders
# ---------------------------------------------------------------------------


def build_scene_prompt_deterministic(
    scene_name: str,
    time_of_day: str = "",
    weather: str = "",
    lighting: str = "",
    mood: str = "",
    color_palette: list[str] | None = None,
    anchors: list[str] | None = None,
    foreground: list[str] | None = None,
    midground: list[str] | None = None,
    background: list[str] | None = None,
) -> str:
    """Build a deterministic scene_prompt from scene attributes.

    The prompt describes the scene visually without referencing any characters.
    """
    parts: list[str] = [f"一个{scene_name}"]

    if time_of_day:
        parts.append(f"时间是{time_of_day}")
    if weather:
        parts.append(f"天气为{weather}")
    if lighting:
        parts.append(f"光线效果为{lighting}")
    if mood:
        parts.append(f"氛围{not mood.startswith('氛围') and '为' or ''}{mood}")
    if color_palette:
        parts.append(f"色调为{'、'.join(color_palette)}")

    # Spatial description
    spatial: list[str] = []
    if background:
        spatial.append(f"背景有{'、'.join(background)}")
    if midground:
        spatial.append(f"中景有{'、'.join(midground)}")
    if foreground:
        spatial.append(f"前景有{'、'.join(foreground)}")

    if spatial:
        parts.append("空间构成：" + "；".join(spatial) + "。")

    if anchors:
        parts.append(f"场景标志性元素包括{'、'.join(anchors)}。")

    return "，".join(parts) + "。"


def build_empty_scene_prompt_deterministic(
    scene_prompt: str,
    time_of_day: str = "",
    weather: str = "",
    lighting: str = "",
    mood: str = "",
) -> str:
    """Build a deterministic empty_scene_prompt.

    Always starts with "不能出现其他人，无人纯场景，" and includes
    "no humans, empty scene, landscape only".
    """
    # Strip trailing punctuation for clean joining
    clean_prompt = scene_prompt.rstrip("。！？,.!? ")

    atmosphere_parts: list[str] = [clean_prompt]
    if time_of_day:
        atmosphere_parts.append(f"{time_of_day}")
    if weather:
        atmosphere_parts.append(f"{weather}")
    if lighting:
        atmosphere_parts.append(f"{lighting}光线")
    if mood:
        atmosphere_parts.append(f"{mood}氛围")

    scene_desc = "，".join(atmosphere_parts) + "。"
    atmosphere_addon = (
        f"{time_of_day}，{weather}，{lighting}，{mood}氛围。" if any([time_of_day, weather, lighting, mood]) else ""
    )

    return (
        f"不能出现其他人，无人纯场景，{scene_desc}no humans, empty scene, landscape only, {atmosphere_addon}"
    ).strip()


# ---------------------------------------------------------------------------
# LLM-assisted prompt refinement
# ---------------------------------------------------------------------------


async def refine_prompts_with_llm(
    provider: TextGenerationProvider,
    scene_name: str,
    scene_type: str,
    time_of_day: str,
    weather: str,
    lighting: str,
    mood: str,
    color_palette: list[str],
    anchors: list[str],
    foreground: list[str],
    midground: list[str],
    background: list[str],
    deterministic_scene_prompt: str,
    deterministic_empty_prompt: str,
) -> tuple[str, str]:
    """Use LLM to refine scene_prompt and empty_scene_prompt.

    Falls back to deterministic output if LLM fails.
    """
    import json as _json

    system_prompt = (
        "你是一个场景视觉描述助手。请根据场景信息生成两个 prompt：\n\n"
        "1. scene_prompt: 场景的详细视觉描述，用于生成场景图像。"
        "必须是一段连贯的中文描述文字，不要列出字段。"
        "绝对不要包含任何角色姓名。\n\n"
        "2. empty_scene_prompt: 空场景 prompt。必须严格以「不能出现其他人，无人纯场景，」开头，"
        "然后跟场景描述，必须以「no humans, empty scene, landscape only」结尾或紧跟其后，"
        "后面可跟光线/天气/氛围信息。"
        "空场景 prompt 中绝对不能有任何人，纯无人场景。\n\n"
        '返回 JSON: {"scene_prompt": "...", "empty_scene_prompt": "..."}'
    )

    scene_info: dict[str, Any] = {
        "场景名称": scene_name,
        "场景类型": scene_type,
        "时段": time_of_day,
        "天气": weather,
        "光照": lighting,
        "氛围": mood,
        "色调": color_palette,
        "固定锚点": anchors,
        "前景元素": foreground,
        "中景元素": midground,
        "背景元素": background,
    }

    prompt = (
        f"场景信息:\n{_json.dumps(scene_info, ensure_ascii=False, indent=2)}\n\n"
        f"已有的确定性 scene_prompt: {deterministic_scene_prompt}\n"
        f"已有的确定性 empty_scene_prompt: {deterministic_empty_prompt}\n\n"
        "请生成更详细、更具视觉表现力的两个 prompt。"
        "empty_scene_prompt 必须以「不能出现其他人，无人纯场景，」开头。"
    )

    try:
        request = TextGenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=2048,
            timeout_seconds=30,
        )
        response = await provider.generate_json(request)

        if response.json_data:
            refined_scene = response.json_data.get("scene_prompt", deterministic_scene_prompt)
            refined_empty = response.json_data.get("empty_scene_prompt", deterministic_empty_prompt)
            if isinstance(refined_scene, str) and isinstance(refined_empty, str):
                # Ensure empty_scene_prompt starts with the required prefix
                if not refined_empty.startswith("不能出现其他人，无人纯场景，"):
                    refined_empty = f"不能出现其他人，无人纯场景，{refined_empty}"
                # Ensure no humans clause is present
                if "no humans" not in refined_empty.lower():
                    refined_empty += " no humans, empty scene, landscape only."
                return str(refined_scene), str(refined_empty)
    except Exception:
        pass

    return deterministic_scene_prompt, deterministic_empty_prompt


# ---------------------------------------------------------------------------
# Scene name validation
# ---------------------------------------------------------------------------


def validate_scene_name(name: str, provider: TextGenerationProvider | None = None) -> tuple[bool, str, str]:
    """Validate and potentially expand a scene name.

    Rules:
    - Must have at least 4 Chinese characters.
    - Cannot be made only of generic words.

    Returns:
        (is_valid, error_message, suggested_expanded_name)
    """
    import re

    name = name.strip()
    chinese_chars = re.findall(r"[一-鿿]", name)

    if len(chinese_chars) < 4:
        return False, f'场景名称 "{name}" 的中文字符不足4个（当前{len(chinese_chars)}个）', ""

    # Check for purely generic names
    generic_patterns = [
        r"^一个?[房间厅堂楼阁院]{1,3}$",
        r"^[东南西北]?[房间厅]{1,2}$",
        r"^[大小][房间厅]{1,2}$",
    ]

    for pattern in generic_patterns:
        if re.match(pattern, name):
            return False, f'场景名称 "{name}" 过于通用，请使用更具体的名称', ""

    return True, "", ""


async def expand_short_name(
    provider: TextGenerationProvider,
    name: str,
    description: str,
    anchors: list[str],
) -> str:
    """Use LLM to expand a short scene name into a 4+ Chinese character name.

    Falls back to appending description keywords if LLM fails.
    """
    import re

    chinese_chars = re.findall(r"[一-鿿]", name)
    if len(chinese_chars) >= 4:
        return name

    system_prompt = (
        "你是一个场景命名助手。请将过于简短或通用的场景名称扩展为具体的、"
        "包含空间特征的名称（至少4个中文字符）。\n"
        '例如: "办公室" → "总裁顶层办公室", "房间" → "温馨少女卧室", '
        '"大厅" → "豪华酒店大堂"。\n'
        "返回扩展后的名称（纯文本），不要带引号或额外说明。"
    )

    anchor_str = "、".join(anchors) if anchors else "无特定元素"
    prompt = (
        f"原场景名称: {name}\n"
        f"场景描述: {description}\n"
        f"场景元素: {anchor_str}\n\n"
        "请给出扩展后的场景名称（至少4个中文字符）。"
    )

    try:
        request = TextGenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=64,
            timeout_seconds=15,
        )
        response = await provider.generate(request)
        expanded = response.text.strip()
        chinese_in_expanded = re.findall(r"[一-鿿]", expanded)
        if len(chinese_in_expanded) >= 4:
            return expanded
    except Exception:
        pass

    # Fallback: prepend descriptive keywords
    desc_words = description.split(";")[0] if description else ""
    desc_chars = re.findall(r"[一-鿿]", desc_words)
    prefix = "".join(desc_chars[:4]) if len(desc_chars) >= 2 else "具体"

    return f"{prefix}{name}"


# ---------------------------------------------------------------------------
# Forbidden elements
# ---------------------------------------------------------------------------


def build_forbidden_elements() -> list[str]:
    """Return the standard forbidden elements list for all scene images.

    Scenes must NOT contain: people, text/watermarks/logos.
    """
    return [
        "人物",
        "角色",
        "人类",
        "文字",
        "水印",
        "logo",
        "字幕",
        "品牌标识",
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def build_scene_prompts(
    provider: TextGenerationProvider,
    scene_name: str,
    scene_type: str,
    time_of_day: str,
    weather: str,
    lighting: str,
    mood: str,
    color_palette: list[str],
    anchors: list[str],
    foreground: list[str],
    midground: list[str],
    background: list[str],
    use_llm: bool = True,
) -> tuple[str, str]:
    """Generate scene_prompt and empty_scene_prompt for a scene.

    Args:
        provider: LLM provider for prompt refinement.
        scene_name: Validated scene name (>= 4 Chinese chars).
        scene_type: Scene type (室内/室外/混合).
        time_of_day: Time of day.
        weather: Weather condition.
        lighting: Lighting description.
        mood: Mood/atmosphere.
        color_palette: Color palette list.
        anchors: Fixed anchors list.
        foreground: Foreground elements.
        midground: Midground elements.
        background: Background elements.
        use_llm: Whether to use LLM refinement.

    Returns:
        (scene_prompt, empty_scene_prompt) tuple.
    """
    det_scene_prompt = build_scene_prompt_deterministic(
        scene_name=scene_name,
        time_of_day=time_of_day,
        weather=weather,
        lighting=lighting,
        mood=mood,
        color_palette=color_palette,
        anchors=anchors,
        foreground=foreground,
        midground=midground,
        background=background,
    )

    det_empty_prompt = build_empty_scene_prompt_deterministic(
        scene_prompt=det_scene_prompt,
        time_of_day=time_of_day,
        weather=weather,
        lighting=lighting,
        mood=mood,
    )

    if use_llm:
        return await refine_prompts_with_llm(
            provider=provider,
            scene_name=scene_name,
            scene_type=scene_type,
            time_of_day=time_of_day,
            weather=weather,
            lighting=lighting,
            mood=mood,
            color_palette=color_palette,
            anchors=anchors,
            foreground=foreground,
            midground=midground,
            background=background,
            deterministic_scene_prompt=det_scene_prompt,
            deterministic_empty_prompt=det_empty_prompt,
        )

    return det_scene_prompt, det_empty_prompt
