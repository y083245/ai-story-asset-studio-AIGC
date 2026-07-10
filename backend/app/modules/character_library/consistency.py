"""Consistency tag and forbidden-changes generation.

Given a character profile, this module produces:
1. `consistency_tag` — a comma-separated key=value string for prompt injection.
2. `forbidden_changes` — a list of human-readable constraints for image generation.

The LLM is used for refinement; deterministic fallbacks are always available.
"""

from __future__ import annotations

from typing import Any

from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest

# ---------------------------------------------------------------------------
# Deterministic consistency_tag builder (no LLM required)
# ---------------------------------------------------------------------------


def build_consistency_tag_deterministic(profile: dict[str, Any]) -> str:
    """Build a consistency tag string from character profile fields.

    Format: "key:value, key:value, ..."
    Only non-empty fields are included.
    """
    parts: list[str] = []

    mapping = [
        ("性别", "gender"),
        ("年龄", "age"),
        ("身高", "height"),
        ("体型", "body_type"),
        ("脸型", "face_shape"),
        ("眼型", "eyes"),
        ("鼻型", "nose"),
        ("嘴型", "mouth"),
        ("发型", "hair_style"),
        ("发色", "hair_color"),
        ("肤色", "skin_tone"),
        ("服装", "default_outfit"),
        ("身份", "identity"),
    ]

    for label, key in mapping:
        value = profile.get(key)
        if value and str(value).strip():
            parts.append(f"{label}:{value}")

    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Deterministic forbidden_changes builder
# ---------------------------------------------------------------------------


def build_forbidden_changes_deterministic(profile: dict[str, Any]) -> list[str]:
    """Build a list of forbidden changes from non-empty character fields.

    Each entry is a human-readable string like "发型为黑色长直发不可变".
    """
    items: list[str] = []

    rules = [
        ("脸部特征", ["face_shape", "eyes", "nose", "mouth", "eyebrows"]),
        ("脸型", ["face_shape"]),
        ("眼型", ["eyes"]),
        ("鼻型", ["nose"]),
        ("嘴型", ["mouth"]),
        ("眉型", ["eyebrows"]),
        ("发型", ["hair_style", "hair_color"]),
        ("发色", ["hair_color"]),
        ("肤色", ["skin_tone"]),
        ("体型", ["body_type", "height"]),
        ("身高", ["height"]),
    ]

    # Deduplicate by checking unique field-value pairs
    emitted: set[str] = set()

    for label, keys in rules:
        values = []
        for k in keys:
            v = profile.get(k)
            if v and str(v).strip():
                values.append(str(v))

        if values:
            # For composite groups, skip if we already emitted individual items
            detail = "、".join(values)
            text = f"{label}为{detail}不可变"
            if text not in emitted and len(text) <= 100:
                emitted.add(text)

    # Always add a clothing constraint if outfit is set
    outfit = profile.get("default_outfit")
    if outfit and str(outfit).strip():
        items.append(f"服装为{outfit}不可变")

    # Add personality constraint
    personality = profile.get("personality")
    if personality and str(personality).strip():
        items.append(f"气质{personality}不可变")

    return items


# ---------------------------------------------------------------------------
# LLM-assisted refinement (optional, for quality)
# ---------------------------------------------------------------------------


async def refine_consistency_with_llm(
    provider: TextGenerationProvider,
    profile: dict[str, Any],
    deterministic_tag: str,
    deterministic_forbidden: list[str],
) -> tuple[str, list[str]]:
    """Use the LLM to refine consistency_tag and forbidden_changes.

    The LLM is given the deterministic output and asked to improve it.
    Falls back to deterministic output if the LLM fails.
    """
    system_prompt = (
        "你是一个角色一致性助手。你的任务是为角色生成一致性标签 (consistency_tag) "
        "和禁止修改列表 (forbidden_changes)。\n"
        'consistency_tag 格式: 逗号分隔的 key:value, 例如 "性别:女, 年龄:28岁, 脸型:鹅蛋脸"\n'
        'forbidden_changes: 字符串列表, 例如 ["脸部特征不可变", "发型为黑色长直发不可变"]\n\n'
        "规则:\n"
        "1. 只包含确实描述角色固定特征的项。\n"
        "2. 禁止修改列表应该覆盖角色的核心不可变特征 (脸型、五官、发型、体型、服装、气质)。\n"
        "3. 不要编造不存在的特征。\n"
        '4. 返回 JSON: {"consistency_tag": "...", "forbidden_changes": ["...", ...]}'
    )

    import json as _json

    prompt = (
        "角色信息:\n"
        + _json.dumps(profile, ensure_ascii=False, indent=2)
        + "\n\n"
        + f"已有的 deterministic consistency_tag: {deterministic_tag}\n"
        + f"已有的 deterministic forbidden_changes: {deterministic_forbidden}\n\n"
        + "请优化以上结果，返回更精确的 JSON。"
    )

    try:
        request = TextGenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1024,
            timeout_seconds=30,
        )
        response = await provider.generate_json(request)

        if response.json_data:
            refined_tag = response.json_data.get("consistency_tag", deterministic_tag)
            refined_forbidden = response.json_data.get("forbidden_changes", deterministic_forbidden)
            if isinstance(refined_tag, str) and isinstance(refined_forbidden, list):
                return str(refined_tag), [str(f) for f in refined_forbidden]
    except Exception:
        pass

    return deterministic_tag, deterministic_forbidden


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_consistency(
    provider: TextGenerationProvider,
    profile: dict[str, Any],
    use_llm: bool = True,
) -> tuple[str, list[str]]:
    """Generate consistency_tag and forbidden_changes for a character.

    Args:
        provider: LLM provider for optional refinement.
        profile: Character profile dict with physical/trait fields.
        use_llm: Whether to use LLM refinement (default True).

    Returns:
        (consistency_tag, forbidden_changes) tuple.
    """
    tag = build_consistency_tag_deterministic(profile)
    forbidden = build_forbidden_changes_deterministic(profile)

    if use_llm:
        tag, forbidden = await refine_consistency_with_llm(provider, profile, tag, forbidden)

    return tag, forbidden
