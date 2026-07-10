"""Scene alias merging logic for the Scene Library module.

Given a list of CandidateSceneInput (from M05 Text Understanding), this module:
1. Merges exact-name duplicates (after normalizing whitespace/punctuation).
2. Uses LLM-assisted merging to resolve scene aliases to canonical names.
3. Falls back to exact-match only when the LLM call fails.

Scene merging rules:
- "顶层办公室" / "总裁办公室" / "CEO办公室" → merge into one canonical name
- "公司大堂" / "一楼大厅" → merge if they refer to the same space
- Different locations (e.g. "办公室" vs "咖啡厅") stay separate
"""

from __future__ import annotations

from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest
from app.modules.scene_library.schemas import CandidateSceneInput

# ---------------------------------------------------------------------------
# Deterministic merge — exact name match (normalized)
# ---------------------------------------------------------------------------


def _normalise_name(name: str) -> str:
    """Normalise a scene name for comparison.

    Strips surrounding whitespace, collapses interior whitespace,
    and removes common punctuation differences.
    """
    import re

    result = name.strip()
    # Collapse whitespace
    result = " ".join(result.split())
    # Remove Chinese/English punctuation for fuzzy comparison
    result = re.sub(r"[，。！？、；：'（）【】《》\[\]\s\-_—]", "", result)
    return result


def _exact_dedup(candidates: list[CandidateSceneInput]) -> list[CandidateSceneInput]:
    """Merge candidates with exactly matching normalized names."""
    name_map: dict[str, CandidateSceneInput] = {}
    for c in candidates:
        key = _normalise_name(c.name)
        if key in name_map:
            existing = name_map[key]
            # Merge anchors
            for a in c.anchors:
                if a not in existing.anchors:
                    existing.anchors.append(a)
            # Merge descriptions
            if c.description:
                existing.description = (
                    f"{existing.description}; {c.description}" if existing.description else c.description
                )
            # Keep the first non-empty time
            if c.time and not existing.time:
                existing.time = c.time
        else:
            name_map[key] = c

    return list(name_map.values())


# ---------------------------------------------------------------------------
# LLM-assisted semantic merge
# ---------------------------------------------------------------------------


async def _llm_merge_candidates(
    provider: TextGenerationProvider, candidates: list[CandidateSceneInput]
) -> list[dict[str, object]]:
    """Use the LLM to identify which candidates refer to the same scene.

    Returns a list of merged groups, where each group has a canonical name
    and a list of aliases.

    Fallback: if the provider call fails, returns each candidate as its own
    group with no merge.
    """
    candidate_lines: list[str] = []
    for i, c in enumerate(candidates, start=1):
        candidate_lines.append(
            f"{i}. 场景名: {c.name}, 时段: {c.time}, "
            f"锚点: {', '.join(c.anchors) if c.anchors else '无'}, "
            f"描述: {c.description or '无'}"
        )

    system_prompt = (
        "你是一个场景去重助手。你的任务是将指代同一空间/地点的场景名称合并为一个规范名。\n"
        "合并规则:\n"
        "1. 完全相同的名字直接合并。\n"
        "2. 同一地点的不同称呼（如「顶层办公室」「总裁办公室」「CEO办公室」）合并为一个规范名，"
        "规范名应为最完整、最具描述性的名称。\n"
        "3. 同一空间的子区域（如「公司大堂」「一楼大厅」）如确为同一场景则合并。\n"
        "4. 不同的独立场景（如「办公室」与「咖啡厅」）不要合并。\n"
        "5. 合并后必须保留一个 canonical_name 和所有已知的 aliases。\n\n"
        "请返回一个 JSON, 包含 merged 列表, 每项有 canonical_name, aliases 和 merged_indices (输入序号, 从1开始)。\n"
        "如果所有场景都不同，则每个场景单独成组。"
    )

    prompt = (
        "以下是待合并的场景候选列表:\n\n"
        + "\n".join(candidate_lines)
        + '\n\n返回 JSON 格式: {"merged": [{"canonical_name": "...", "aliases": ["..."], "merged_indices": [1, 2]}, ...]}'
    )

    try:
        request = TextGenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2048,
            timeout_seconds=30,
        )
        response = await provider.generate_json(request)

        if response.json_data and "merged" in response.json_data:
            return response.json_data["merged"]  # type: ignore[no-any-return]
    except Exception:
        pass

    # Fallback: no merge — every candidate is its own group
    fallback: list[dict[str, object]] = []
    for i, c in enumerate(candidates, start=1):
        fallback.append(
            {
                "canonical_name": c.name,
                "aliases": [],
                "merged_indices": [i],
            }
        )
    return fallback


def _merge_by_indices(
    candidates: list[CandidateSceneInput],
    merge_groups: list[dict[str, object]],
) -> list[CandidateSceneInput]:
    """Given merge groups, produce a deduplicated candidate list.

    For each group:
    - Use canonical_name as the name.
    - Collect all aliases from the group.
    - Merge anchors and description from all merged members.
    - Use the first member's time.
    """
    merged: list[CandidateSceneInput] = []
    seen_indices: set[int] = set()

    for group in merge_groups:
        canonical = str(group["canonical_name"])
        indices_raw = group.get("merged_indices", [])
        indices: list[int] = [int(i) for i in indices_raw] if isinstance(indices_raw, list) else []

        merged_anchors: list[str] = []
        merged_description_parts: list[str] = []
        first_time = ""

        for idx in indices:
            c_idx = idx - 1  # convert to 0-based
            if c_idx < 0 or c_idx >= len(candidates):
                continue
            seen_indices.add(idx)
            c = candidates[c_idx]

            if not first_time and c.time:
                first_time = c.time

            for a in c.anchors:
                if a not in merged_anchors:
                    merged_anchors.append(a)
            if c.description:
                merged_description_parts.append(c.description)

        merged.append(
            CandidateSceneInput(
                name=_normalise_name(canonical),
                time=first_time,
                description="; ".join(merged_description_parts),
                anchors=merged_anchors,
            )
        )

    # Add any unmerged candidates
    for i, c in enumerate(candidates, start=1):
        if i not in seen_indices:
            merged.append(c)

    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def merge_scene_aliases(
    provider: TextGenerationProvider,
    candidates: list[CandidateSceneInput],
) -> list[CandidateSceneInput]:
    """Merge duplicate/alias scene candidates into a deduplicated list.

    Args:
        provider: An LLM provider for semantic alias resolution.
        candidates: Raw candidate scenes from M05.

    Returns:
        A deduplicated list of CandidateSceneInput.
    """
    if len(candidates) <= 1:
        return candidates

    # Step 1: Exact-name dedup (deterministic, fast-path)
    exact_dedup = _exact_dedup(candidates)

    if len(exact_dedup) <= 1:
        return exact_dedup

    # Step 2: LLM-assisted semantic merge
    merge_groups = await _llm_merge_candidates(provider, exact_dedup)

    return _merge_by_indices(exact_dedup, merge_groups)
