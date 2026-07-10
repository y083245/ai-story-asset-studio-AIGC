"""State timeline generation and validation for the Prop Library module.

- Core props MUST have at least 2 state timeline entries.
- Supporting props SHOULD have at least 1 entry.
- Minor props may have 0 entries without blocking.
"""

from __future__ import annotations

from app.modules.prop_library.schemas import CandidatePropInput, StateTimelineItem


def generate_state_timeline(
    candidate: CandidatePropInput,
    chapter_text: list[str] | None = None,
) -> list[StateTimelineItem]:
    """Generate a state timeline for a prop based on its description and chapter context.

    Args:
        candidate: The merged candidate prop.
        chapter_text: Optional chapter texts for context-aware timeline generation.

    Returns:
        A list of StateTimelineItem entries.
    """
    timeline: list[StateTimelineItem] = []

    # Attempt to parse state changes from the description and function_hint
    desc = candidate.description or ""
    func = candidate.function_hint or ""

    # Common state patterns from story prop usage.
    state_keywords = {
        "出现": "首次出现",
        "拿出": "被取出/拿出",
        "放在": "被放置",
        "手持": "被手持",
        "交给": "被转交",
        "摔": "被摔碎/破坏",
        "丢": "被丢弃/丢失",
        "毁": "被毁坏",
        "找回": "被找回",
        "修复": "被修复",
        "佩戴": "被佩戴",
        "展示": "被展示",
        "发现": "被发现",
        "隐藏": "被隐藏",
        "使用": "被使用",
        "归还": "被归还",
    }

    step_index = 0
    combined = desc + func

    for keyword, state_desc in state_keywords.items():
        if keyword in combined:
            step_index += 1
            timeline.append(
                StateTimelineItem(step_index=step_index, state=state_desc, description=f"基于候选描述: {keyword}")
            )

    # If chapter_text is provided, add chapter-based entries
    if chapter_text:
        for i, chapter in enumerate(chapter_text):
            if candidate.name in chapter or any(alias in chapter for alias in candidate.aliases):
                step_index += 1
                timeline.append(
                    StateTimelineItem(
                        step_index=step_index,
                        state=f"第{i + 1}章出现",
                        description=f"在章节文本中被提及: {chapter[:80]}...",
                    )
                )

    return timeline


def validate_timeline_for_importance(
    importance: str,
    timeline: list[StateTimelineItem],
    prop_name: str,
) -> list[str]:
    """Validate that the state timeline meets requirements for the given importance level.

    Args:
        importance: One of "core", "supporting", "minor".
        timeline: The current state timeline entries.
        prop_name: The prop name for error messages.

    Returns:
        A list of blocking error messages (empty if valid).
    """
    errors: list[str] = []

    if importance == "core" and len(timeline) < 2:
        errors.append(
            f"Core prop '{prop_name}' must have at least 2 state timeline entries, but only {len(timeline)} found."
        )
    # Supporting props should have at least 1 entry, but this is a warning, not a block
    # minor: no minimum requirement, never blocks

    return errors
