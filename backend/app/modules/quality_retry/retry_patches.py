"""Retry patch generation for image assets.

Builds retry prompt patches based on detected quality issues.
Each issue type maps to a specific patch generation strategy.
"""

from __future__ import annotations

from typing import Any


def build_face_fix_patch(
    character_id: str,
    issue_detail: dict[str, str] | None = None,
) -> str:
    """Build retry patch for face inconsistency (M13-09).

    Strategies:
    - Strengthen character reference image
    - Reduce pose complexity
    - Use a clearer crop or half-body composition

    Args:
        character_id: The character ID (e.g., "CH_001").
        issue_detail: Optional additional details about the issue.

    Returns:
        A prompt patch string for face fix.
    """
    parts = [
        f"【面部修复 - {character_id}】",
        "强化角色参考图的面部特征约束",
        "降低姿态复杂度，保持面部清晰稳定",
    ]

    detail_msg = ""
    if issue_detail:
        detail_msg = issue_detail.get("description", "")
        if detail_msg:
            parts.append(f"具体问题: {detail_msg}")

    parts.append("尝试改用近景或半身构图以突出面部细节")
    parts.append("重新生成角色参考图，减少面部变形")

    return "；".join(parts)


def build_scene_fix_patch(
    scene_id: str,
    fixed_anchors: list[str],
    issue_detail: dict[str, str] | None = None,
) -> str:
    """Build retry patch for scene mismatch (M13-10).

    Strategies:
    - Strengthen fixed_anchors
    - Use empty scene reference image
    - Use a simpler composition

    Args:
        scene_id: The scene ID (e.g., "SC_001").
        fixed_anchors: List of fixed anchor elements.
        issue_detail: Optional additional details about the issue.

    Returns:
        A prompt patch string for scene fix.
    """
    parts = [
        f"【场景修复 - {scene_id}】",
    ]

    if fixed_anchors:
        anchors_str = "、".join(fixed_anchors[:5])
        parts.append(f"强化以下固定锚点: {anchors_str}")
    else:
        parts.append("强化场景参考图的固定锚点")

    if issue_detail:
        detail_msg = issue_detail.get("description", "")
        if detail_msg:
            parts.append(f"具体问题: {detail_msg}")

    parts.append("使用空场景参考图作为背景基线")
    parts.append("减少构图复杂度，保持场景布局稳定")

    return "；".join(parts)


def build_prop_fix_patch(
    prop_id: str,
    issue_detail: dict[str, str] | None = None,
) -> str:
    """Build retry patch for missing prop (M13-11).

    Strategies:
    - Put prop in core action
    - Add a close-up reference or product-only image

    Args:
        prop_id: The prop ID (e.g., "PR_001").
        issue_detail: Optional additional details about the issue.

    Returns:
        A prompt patch string for prop fix.
    """
    parts = [
        f"【道具修复 - {prop_id}】",
        "将道具放入核心动作描述中",
    ]

    if issue_detail:
        detail_msg = issue_detail.get("description", "")
        if detail_msg:
            parts.append(f"具体问题: {detail_msg}")

    parts.append("增加道具细节参考图")
    parts.append("先生成纯白背景道具单品图，再用于使用图")

    return "；".join(parts)


# Mapping from issue code to patch builder function signature info
ISSUE_TO_PATCH_BUILDER: dict[str, str] = {
    "FACE_CHANGED": "face",
    "FACE_UNSTABLE": "face",
    "OUTFIT_MISMATCH": "outfit",
    "OUTFIT_CHANGE": "outfit",
    "SCENE_MISMATCH": "scene",
    "SCENE_JUMP": "scene",
    "PROP_MISSING": "prop",
}


def build_retry_patches(
    issues: list[dict[str, Any]],
    context: dict[str, Any],
) -> list[str]:
    """Build all applicable retry patches from issue list.

    Args:
        issues: List of issue dicts, each with at least a "code" key.
        context: Dict with character_id, scene_id, prop_ids,
                 fixed_anchors etc.

    Returns:
        List of patch strings, one per applicable issue type.
    """
    patches: list[str] = []
    seen_types: set[str] = set()

    for issue in issues:
        code = issue.get("code", "")
        builder_type = ISSUE_TO_PATCH_BUILDER.get(code)

        if builder_type is None:
            continue

        if builder_type in seen_types:
            continue
        seen_types.add(builder_type)

        if builder_type == "face":
            character_id = context.get("character_id", "")
            patches.append(build_face_fix_patch(str(character_id), issue))
        elif builder_type == "outfit":
            character_id = context.get("character_id", "")
            patches.append(f"【服装修复 - {character_id}】；强化服装参考图约束；确保服装细节一致")
        elif builder_type == "scene":
            scene_id = context.get("scene_id", "")
            fixed_anchors = context.get("fixed_anchors", [])
            patches.append(build_scene_fix_patch(str(scene_id), list(fixed_anchors), issue))
        elif builder_type == "prop":
            prop_ids = context.get("prop_ids", [])
            prop_id = prop_ids[0] if prop_ids else ""
            patches.append(build_prop_fix_patch(str(prop_id), issue))

    return patches
