"""Scene-extractor output normalizer."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.modules.template_style.style_alias import DEFAULT_STYLE_ID
from app.modules.workflow.normalizers.common import as_list, dict_of, field, string_list

SCENE_PROMPT_PREFIX = "不能出现其他人，无人，纯场景，"
SCENE_LEGACY_PREFIX = "不能出现其他人，无人纯场景，"
SCENE_NO_HUMANS_CLAUSE = "no humans,empty,landscape only"


def normalize_scenes(items: list[Any], *, style_id: str = DEFAULT_STYLE_ID) -> list[dict[str, Any]]:  # noqa: ARG001
    result: list[dict[str, Any]] = []
    for index, value in enumerate(items, 1):
        item = dict_of(value)
        name = _scene_name(str(item.get("name") or item.get("scene_name") or f"场景{index}"))
        anchors = _ensure_scene_anchors(
            string_list(item.get("fixed_anchors") or item.get("anchors"))
            + string_list(item.get("foreground_elements"))
            + string_list(item.get("midground_elements"))
            + string_list(item.get("background_elements")),
            name,
        )
        description = str(item.get("description") or name)
        empty_prompt = str(item.get("empty_scene_prompt") or item.get("scene_prompt") or "")
        if settings.prompt_engine_mode == "legacy":
            empty_prompt = _ensure_empty_scene_prompt(
                empty_prompt,
                name=name,
                scene_type=str(item.get("scene_type") or item.get("type") or "室内"),
                time_of_day=str(item.get("time_of_day") or item.get("time") or ""),
                weather=str(item.get("weather") or ""),
                lighting=str(item.get("lighting") or ""),
                mood=str(item.get("mood") or ""),
                anchors=anchors,
            )
            needs_synthesis = None
        else:
            needs_synthesis = not _validate_scene_prompt(empty_prompt)
        result.append(
            {
                "scene_id": str(item.get("scene_id") or f"SC_{index:03d}"),
                "name": name,
                "scene_name": name,
                "scene_type": str(item.get("scene_type") or item.get("type") or "室内"),
                "time_of_day": str(item.get("time_of_day") or item.get("time") or ""),
                "weather": str(item.get("weather") or ""),
                "lighting": str(item.get("lighting") or ""),
                "mood": str(item.get("mood") or ""),
                "color_palette": string_list(item.get("color_palette")),
                "fixed_anchors": anchors,
                "foreground_elements": string_list(item.get("foreground_elements")),
                "midground_elements": string_list(item.get("midground_elements")),
                "background_elements": string_list(item.get("background_elements")),
                "description": description,
                "empty_scene_prompt": empty_prompt,
                **(
                    {}
                    if needs_synthesis is None
                    else {"empty_scene_prompt_needs_synthesis": needs_synthesis}
                ),
                "forbidden_elements": _ensure_forbidden_elements(item.get("forbidden_elements")),
            }
        )
    return result


# ── helpers ──────────────────────────────────────────────────────────


def _scene_name(name: str) -> str:
    clean = name.strip() or "未命名场景"
    if len(re.findall(r"[一-鿿]", clean)) >= 4:
        return clean
    return f"{clean}空间"


def _ensure_scene_anchors(values: list[str], scene_name: str) -> list[str]:
    anchors: list[str] = []
    for value in values:
        text = value.strip()
        if text and text not in anchors:
            anchors.append(text)
    fallback = [f"{scene_name}主体结构", "前景固定物件", "中景核心陈设", "背景空间层次"]
    for value in fallback:
        if len(anchors) >= 3:
            break
        if value not in anchors:
            anchors.append(value)
    return anchors


def _validate_scene_prompt(prompt: str) -> bool:
    text = prompt.strip().lower()
    if not text:
        return False
    people_content_cues = ("人物", "角色", "人影", "站在", "坐在", "手持", "走进", "翻看")
    english_check_text = text.replace("no humans", "").replace("no human", "")
    english_people_pattern = r"\b(woman|man|person|people|human|humans|walking|walks|walk|standing|sitting|holding)\b"
    if any(cue in text for cue in people_content_cues) or re.search(english_people_pattern, english_check_text):
        return False
    semantic_cues = ("无人", "纯场景", "empty", "no humans", "landscape only")
    return any(cue in text for cue in semantic_cues)


def _ensure_empty_scene_prompt(
    prompt: str,
    *,
    name: str,
    scene_type: str,
    time_of_day: str,
    weather: str,
    lighting: str,
    mood: str,
    anchors: list[str],
) -> str:
    body = prompt.strip()
    if body.startswith(SCENE_PROMPT_PREFIX):
        body = body.removeprefix(SCENE_PROMPT_PREFIX)
    elif body.startswith(SCENE_LEGACY_PREFIX):
        body = body.removeprefix(SCENE_LEGACY_PREFIX)
    if not body:
        pieces = [
            f"场景名称：{name}",
            f"环境类型：{scene_type}",
            field("具体时间", time_of_day),
            field("天气光线", "，".join(value for value in [weather, lighting] if value)),
            field("空间氛围", mood),
            f"固定锚点：{'、'.join(anchors)}",
        ]
        body = "，".join(piece for piece in pieces if piece)
    text = SCENE_PROMPT_PREFIX + body.lstrip("，, ")
    if SCENE_NO_HUMANS_CLAUSE not in text:
        text = text.rstrip("。；;，, ") + f"，{SCENE_NO_HUMANS_CLAUSE}。"
    return text


def _ensure_forbidden_elements(value: Any) -> list[str]:
    forbidden = string_list(value)
    for item in ("人物", "人影", "角色姓名", "文字", "水印", "logo"):
        if item not in forbidden:
            forbidden.append(item)
    return forbidden


_as_list = as_list


__all__ = ["normalize_scenes", "SCENE_PROMPT_PREFIX", "SCENE_LEGACY_PREFIX", "SCENE_NO_HUMANS_CLAUSE"]
