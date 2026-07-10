"""Character-extractor output normalizer."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.modules.image_asset.turnaround_template import normalize_turnaround_prompt
from app.modules.template_style.style_alias import DEFAULT_STYLE_ID
from app.modules.workflow.normalizers.common import as_list, dict_of, field, string_list


def normalize_characters(items: list[Any], *, style_id: str = DEFAULT_STYLE_ID) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, value in enumerate(items, 1):
        item = dict_of(value)
        name = str(item.get("name") or f"角色{index}")
        role = str(item.get("role") or item.get("role_type") or "配角")
        gender = str(item.get("gender") or "")
        age_range = str(item.get("age_range") or item.get("age") or "")
        description = str(item.get("description") or item.get("personality") or "")
        default_outfit = str(item.get("default_outfit") or item.get("outfit") or "")
        normalized = {
            "character_id": str(item.get("character_id") or f"CH_{index:03d}"),
            "name": name,
            "aliases": string_list(item.get("aliases")),
            "role": role,
            "gender": gender,
            "age_range": age_range,
            "height": str(item.get("height") or ""),
            "body_type": str(item.get("body_type") or ""),
            "face_shape": str(item.get("face_shape") or ""),
            "facial_features": str(item.get("facial_features") or ""),
            "skin_tone": str(item.get("skin_tone") or ""),
            "hair_style": str(item.get("hair_style") or ""),
            "hair_color": str(item.get("hair_color") or ""),
            "eyes": str(item.get("eyes") or ""),
            "identity": str(item.get("identity") or ""),
            "personality": str(item.get("personality") or description),
            "relationship_to_protagonist": str(item.get("relationship_to_protagonist") or ""),
            "first_appearance": str(item.get("first_appearance") or ""),
            "description": description,
            "default_outfit": default_outfit,
            "outfit_details": str(item.get("outfit_details") or ""),
            "shoes": str(item.get("shoes") or ""),
            "accessories": str(item.get("accessories") or ""),
            "front_image_prompt": str(item.get("front_image_prompt") or ""),
            "turnaround_prompt": str(item.get("turnaround_prompt") or ""),
            "forbidden_changes": string_list(item.get("forbidden_changes")),
        }
        character_description = _character_visual_description(normalized)
        normalized["description"] = description or character_description
        if settings.prompt_engine_mode == "legacy":
            normalized["front_image_prompt"] = _ensure_character_front_prompt(
                normalized["front_image_prompt"],
                character_description,
            )
            normalized["turnaround_prompt"] = normalize_turnaround_prompt(
                normalized["turnaround_prompt"],
                character_description,
                style_id=style_id,
            )
        else:
            normalized["front_prompt_needs_synthesis"] = not _validate_character_front_prompt(
                normalized["front_image_prompt"]
            )
            normalized["turnaround_prompt_needs_synthesis"] = not _validate_character_turnaround_prompt(
                normalized["turnaround_prompt"]
            )
        normalized["forbidden_changes"] = normalized["forbidden_changes"] or _default_forbidden_changes(normalized)
        result.append(normalized)
    return result


# ── helpers ──────────────────────────────────────────────────────────


def _character_visual_description(item: dict[str, Any]) -> str:
    defaults = {
        "shoes": "符合角色身份与服装风格的鞋型、颜色和材质",
        "accessories": "符合角色身份的可见配饰或随身物",
        "outfit_details": "领口、袖长、下装、纹理、扣件和层次清楚",
    }
    parts = [
        field("角色名称", item.get("name")),
        field("角色定位", item.get("role")),
        field("性别", item.get("gender")),
        field("年龄", item.get("age_range")),
        field("身高", item.get("height")),
        field("体型", item.get("body_type")),
        field("脸型", item.get("face_shape")),
        field("脸部特征", item.get("facial_features")),
        field("肤色", item.get("skin_tone")),
        field("发型", item.get("hair_style")),
        field("发色", item.get("hair_color")),
        field("眼睛", item.get("eyes")),
        field("身份", item.get("identity")),
        field("性格", item.get("personality")),
        field("形象描述", item.get("description")),
        field("默认服装", item.get("default_outfit")),
        field("服装细节", item.get("outfit_details") or defaults["outfit_details"]),
        field("鞋子", item.get("shoes") or defaults["shoes"]),
        field("配饰", item.get("accessories") or defaults["accessories"]),
    ]
    return "，".join(part for part in parts if part)


def _validate_character_front_prompt(prompt: str) -> bool:
    text = prompt.strip().lower()
    if not text:
        return False
    non_front_cues = ("背影", "背面", "后视", "侧面", "侧身", "back view", "back-view", "rear view", "side view", "side-view")
    if any(cue in text for cue in non_front_cues):
        return False
    front_cues = ("正面", "front view", "front-facing", "frontal")
    body_cues = ("全身", "完整人物", "full body", "full-body")
    return any(cue in text for cue in front_cues) and any(cue in text for cue in body_cues)


def _validate_character_turnaround_prompt(prompt: str) -> bool:
    text = prompt.strip().lower()
    if not text:
        return False
    if any(cue in text for cue in ("三视图", "三面图", "转身图", "turnaround")):
        return True
    has_front = "正面" in text or "front" in text
    has_side = "侧面" in text or "侧身" in text or "side" in text
    has_back = "背面" in text or "背影" in text or "后视" in text or "back" in text or "rear" in text
    return has_front and has_side and has_back


def _ensure_character_front_prompt(prompt: str, character_description: str) -> str:
    text = prompt.strip() or f"{character_description}，正面站立全身，纯白背景，完整人物，不裁切。"
    required_phrases = (
        "正面站立全身",
        "纯白背景",
        "完整人物",
        "不裁切",
        "清楚鞋子",
        "清楚配饰",
    )
    missing = [phrase for phrase in required_phrases if phrase not in text]
    if missing:
        text = text.rstrip("。；;，, ") + "，" + "，".join(missing) + "。"
    return text


def _default_forbidden_changes(item: dict[str, Any]) -> list[str]:
    values = [
        field("五官", item.get("facial_features") or item.get("face_shape")),
        field("发型", item.get("hair_style")),
        field("服装主色和版型", item.get("default_outfit")),
        field("关键配饰", item.get("accessories")),
        field("身份识别点", item.get("identity")),
    ]
    return [value for value in values if value] or ["五官不可变", "发型不可变", "服装主色不可变", "关键配饰不可变"]


# re-exported for tests that used the private names on analysis_activities
__all__ = ["normalize_characters"]

# Keep _as_list / _dict etc. reachable for callers that used to import them
# via the analysis_activities module — cheap aliases so we don't force a
# find-and-replace across the frontend tests.
_as_list = as_list
