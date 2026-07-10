"""Helpers for rendering style-pack character turnaround reference boards."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.modules.template_style.style_pack import StylePackRegistry

TURNAROUND_CHARACTER_PLACEHOLDER = "【人物形象描述]"
TURNAROUND_SECTION_MARKER = "【对应母版原文】"
DEFAULT_TURNAROUND_STYLE_ID = "cinematic_realistic"


def render_turnaround_template(
    character_description: str,
    *,
    style_id: str = DEFAULT_TURNAROUND_STYLE_ID,
    template_text: str | None = None,
) -> str:
    """Render the selected style-pack turnaround template with a character description."""
    clean_description = " ".join(character_description.split())
    template = template_text if template_text is not None else turnaround_template_text_for_style(style_id)
    return _render_template_text(template, clean_description)


def render_turnaround_contract_template(*, style_id: str = DEFAULT_TURNAROUND_STYLE_ID) -> str:
    """Render the selected style-pack template with its document placeholder."""
    return render_turnaround_template(TURNAROUND_CHARACTER_PLACEHOLDER, style_id=style_id)


def turnaround_template_text_for_style(style_id: str) -> str:
    """Return the full character_turnaround_prompt style-pack system prompt."""
    return _cached_turnaround_template_text(style_id)


def is_strict_turnaround_prompt(
    prompt: str,
    *,
    style_id: str = DEFAULT_TURNAROUND_STYLE_ID,
    template_text: str | None = None,
) -> bool:
    """Return True only when all selected style template lines are present in order."""
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return False
    markers = _required_static_markers(template_text or turnaround_template_text_for_style(style_id))
    if not markers:
        return False

    cursor = 0
    for marker in markers:
        index = clean_prompt.find(marker, cursor)
        if index < 0:
            return False
        cursor = index + len(marker)
    return clean_prompt.endswith(markers[-1])


def normalize_turnaround_prompt(
    prompt: str | None,
    fallback_character_description: str,
    *,
    style_id: str = DEFAULT_TURNAROUND_STYLE_ID,
    template_text: str | None = None,
) -> str:
    """Normalize any accepted turnaround prompt back to the selected style template shape."""
    raw_prompt = str(prompt or "").strip()
    template = template_text if template_text is not None else turnaround_template_text_for_style(style_id)
    if is_strict_turnaround_prompt(raw_prompt, template_text=template):
        character_description = _extract_turnaround_character_description(raw_prompt)
        return render_turnaround_template(
            character_description or fallback_character_description,
            template_text=template,
        )
    return render_turnaround_template(fallback_character_description, template_text=template)


def _extract_turnaround_character_description(prompt: str) -> str:
    start_marker = "人物设定:\n"
    end_marker = "\n输出要求:"
    start_index = prompt.find(start_marker)
    end_index = prompt.find(end_marker)
    if start_index < 0 or end_index < 0 or end_index <= start_index:
        return ""
    return prompt[start_index + len(start_marker) : end_index].strip()


@lru_cache(maxsize=16)
def _cached_turnaround_template_text(style_id: str) -> str:
    registry = StylePackRegistry()
    registry.load_all()
    template = registry.get_template(style_id, "character_turnaround_prompt")
    return template.system_prompt.strip()


def _render_template_text(template_text: str, character_description: str) -> str:
    return template_text.replace(TURNAROUND_CHARACTER_PLACEHOLDER, character_description).strip()


def _required_static_markers(template_text: str) -> tuple[str, ...]:
    rendered = _render_template_text(template_text, TURNAROUND_CHARACTER_PLACEHOLDER)
    body = _turnaround_body(rendered)
    return tuple(
        line for line in body.splitlines() if line.strip() and line.strip() != TURNAROUND_CHARACTER_PLACEHOLDER
    )


def _turnaround_body(template_text: str) -> str:
    if TURNAROUND_SECTION_MARKER not in template_text:
        return template_text
    return template_text.split(TURNAROUND_SECTION_MARKER, 1)[1].strip()


def character_description_from_entity(character: Any) -> str:
    """Build the template's 人物设定 block from a Character-like object."""
    parts = [
        _part("角色名称", getattr(character, "name", "")),
        _part("角色定位", getattr(character, "role_type", "")),
        _part("身份", getattr(character, "identity", "")),
        _part("性别", getattr(character, "gender", "")),
        _part("年龄", getattr(character, "age", "")),
        _part("身高", getattr(character, "height", "")),
        _part("体型", getattr(character, "body_type", "")),
        _part(
            "脸部特征",
            "，".join(
                str(value).strip()
                for value in [
                    getattr(character, "face_shape", ""),
                    getattr(character, "facial_bone_structure", ""),
                    getattr(character, "eyebrows", ""),
                    getattr(character, "nose", ""),
                    getattr(character, "mouth", ""),
                ]
                if str(value or "").strip()
            ),
        ),
        _part("肤色", getattr(character, "skin_tone", "")),
        _part("发型", getattr(character, "hair_style", "")),
        _part("发色", getattr(character, "hair_color", "")),
        _part("眼睛", getattr(character, "eyes", "")),
        _part("人物性格", getattr(character, "personality", "")),
        _part("服装", getattr(character, "default_outfit", "")),
        _part("服装细节", getattr(character, "outfit_details", "")),
        _part("鞋子", getattr(character, "shoes", "")),
        _part("配饰", getattr(character, "accessories", "")),
        _part("一致性", getattr(character, "consistency_tag", "")),
    ]
    return "，".join(part for part in parts if part) or str(getattr(character, "name", "角色"))


def _part(label: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"{label}：{text}"
