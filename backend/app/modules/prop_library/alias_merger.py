"""Alias merging logic for the Prop Library module.

Given a list of CandidatePropInput (from M05 Text Understanding), this module:
1. Merges exact-name duplicates.
2. Uses LLM-assisted merging to resolve aliases to canonical names.
3. Returns a deduplicated list ready for Prop creation.
"""

from __future__ import annotations

from app.modules.prop_library.schemas import CandidatePropInput
from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest

# ---------------------------------------------------------------------------
# Deterministic merge — exact name match
# ---------------------------------------------------------------------------


def _normalise_name(name: str) -> str:
    """Normalise a prop name for comparison.

    Strips surrounding whitespace and collapses interior whitespace.
    """
    return " ".join(name.strip().split())


async def _llm_merge_candidates(
    provider: TextGenerationProvider, candidates: list[CandidatePropInput]
) -> list[dict[str, object]]:
    """Use the LLM to identify which candidates refer to the same prop.

    Returns a list of merged groups, where each group has a canonical name
    and a list of aliases.

    Fallback: if the provider call fails, returns each candidate as its own
    group with no merge.
    """
    candidate_lines: list[str] = []
    for i, c in enumerate(candidates, start=1):
        candidate_lines.append(
            f"{i}. 名称: {c.name}, "
            f"描述: {c.description or '无'}, "
            f"别名: {', '.join(c.aliases) if c.aliases else '无'}, "
            f"所属: {c.owner_name or '未知'}, "
            f"首次出场: {c.first_appearance or '未知'}, "
            f"功能: {c.function_hint or '未知'}"
        )

    system_prompt = (
        "你是一个道具去重助手。你的任务是将指代同一道具的名称合并为一个规范名。\n"
        "合并规则:\n"
        "1. 完全相同的名字直接合并。\n"
        '2. 同一物品的不同称呼（如 "戒指/钻戒/那枚戒指"、"黑刃/玄铁短刀/暗影匕首"）合并为一个规范名。\n'
        "3. 合并后必须保留一个 canonical_name 和所有已知的 aliases。\n"
        "4. 多个不同道具不要合并。\n\n"
        "请返回一个 JSON, 包含 merged 列表, 每项有 canonical_name, aliases 和 merged_indices (输入序号, 从1开始)。\n"
        "如果所有道具都不同，则每个道具单独成组。"
    )

    prompt = (
        "以下是待合并的道具候选列表:\n\n"
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
                "aliases": list(c.aliases) if c.aliases else [],
                "merged_indices": [i],
            }
        )
    return fallback


def _merge_by_indices(
    candidates: list[CandidatePropInput],
    merge_groups: list[dict[str, object]],
) -> list[CandidatePropInput]:
    """Given merge groups, produce a deduplicated candidate list.

    For each group:
    - Use canonical_name as the name.
    - Collect all aliases from the group.
    - Merge description and function_hint from all merged members.
    - Use the first member's owner_name and first_appearance.
    """
    merged: list[CandidatePropInput] = []
    seen_indices: set[int] = set()

    for group in merge_groups:
        canonical = str(group["canonical_name"])
        aliases_raw = group.get("aliases", [])
        aliases: list[str] = [str(a) for a in aliases_raw] if isinstance(aliases_raw, list) else []
        indices_raw = group.get("merged_indices", [])
        indices: list[int] = [int(i) for i in indices_raw] if isinstance(indices_raw, list) else []

        merged_description_parts: list[str] = []
        merged_function_parts: list[str] = []
        first_owner = ""
        first_appearance = ""

        for idx in indices:
            c_idx = idx - 1  # convert to 0-based
            if c_idx < 0 or c_idx >= len(candidates):
                continue
            seen_indices.add(idx)
            c = candidates[c_idx]

            if not first_owner and c.owner_name:
                first_owner = c.owner_name
            if not first_appearance and c.first_appearance:
                first_appearance = c.first_appearance

            if c.description:
                merged_description_parts.append(c.description)
            if c.function_hint:
                merged_function_parts.append(c.function_hint)

            # Collect aliases from input
            for a in c.aliases:
                if a and a not in aliases:
                    aliases.append(a)

        # Build full alias list including canonical name
        all_aliases = list(aliases)
        for a in [canonical] + aliases:
            if a and a != canonical and a not in all_aliases:
                all_aliases.append(a)

        merged.append(
            CandidatePropInput(
                name=_normalise_name(canonical),
                description="; ".join(merged_description_parts),
                aliases=all_aliases,
                owner_name=first_owner,
                first_appearance=first_appearance,
                function_hint="; ".join(merged_function_parts),
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


async def merge_prop_aliases(
    provider: TextGenerationProvider,
    candidates: list[CandidatePropInput],
) -> list[CandidatePropInput]:
    """Merge duplicate/alias candidates into a deduplicated list.

    Args:
        provider: An LLM provider for semantic alias resolution.
        candidates: Raw candidate props from M05.

    Returns:
        A deduplicated list of CandidatePropInput.
    """
    if len(candidates) <= 1:
        return candidates

    # Step 1: Exact-name dedup (deterministic, fast-path)
    name_map: dict[str, CandidatePropInput] = {}
    for c in candidates:
        key = _normalise_name(c.name)
        if key in name_map:
            existing = name_map[key]
            for a in c.aliases:
                if a not in existing.aliases:
                    existing.aliases.append(a)
            if c.description:
                existing.description = (
                    f"{existing.description}; {c.description}" if existing.description else c.description
                )
            if c.function_hint and not existing.function_hint:
                existing.function_hint = c.function_hint
            if c.first_appearance and not existing.first_appearance:
                existing.first_appearance = c.first_appearance
            if c.owner_name and not existing.owner_name:
                existing.owner_name = c.owner_name
        else:
            name_map[key] = c

    exact_dedup = list(name_map.values())

    if len(exact_dedup) <= 1:
        return exact_dedup

    # Step 2: LLM-assisted semantic merge
    merge_groups = await _llm_merge_candidates(provider, exact_dedup)

    return _merge_by_indices(exact_dedup, merge_groups)
