"""Alias merging logic for the Character Library module.

Given a list of CandidateCharacter (from M05 Text Understanding), this module:
1. Merges exact-name duplicates.
2. Uses LLM-assisted merging to resolve pronouns/aliases to canonical names.
3. Returns a deduplicated list ready for Character creation.
"""

from __future__ import annotations

from app.modules.character_library.schemas import CandidateCharacterInput
from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest

# ---------------------------------------------------------------------------
# Deterministic merge — exact name match
# ---------------------------------------------------------------------------


def _normalise_name(name: str) -> str:
    """Normalise a character name for comparison.

    Strips surrounding whitespace and collapses interior whitespace.
    """
    return " ".join(name.strip().split())


async def _llm_merge_candidates(
    provider: TextGenerationProvider, candidates: list[CandidateCharacterInput]
) -> list[dict[str, object]]:
    """Use the LLM to identify which candidates refer to the same character.

    Returns a list of merged groups, where each group has a canonical name
    and a list of aliases.

    Fallback: if the provider call fails, returns each candidate as its own
    group with no merge.
    """
    # Build a human-readable candidate list for the prompt
    candidate_lines: list[str] = []
    for i, c in enumerate(candidates, start=1):
        candidate_lines.append(
            f"{i}. 名称: {c.name}, 定位: {c.role}, "
            f"特征: {', '.join(c.traits) if c.traits else '无'}, "
            f"描述: {c.description or '无'}, "
            f"首次出场: {c.first_appearance or '未知'}"
        )

    system_prompt = (
        "你是一个角色去重助手。你的任务是将指代同一角色的名称合并为一个规范名。\n"
        "合并规则:\n"
        "1. 完全相同的名字直接合并。\n"
        "2. '她/女主/男主/那位女士/年轻人' 等代词 → 通过上下文合并到同名角色。\n"
        "3. 同一个人的不同称呼（如 '苏晚' 和 '晚晴' 和 '苏小姐'）合并为一个规范名。\n"
        "4. 合并后必须保留一个 canonical_name 和所有已知的 aliases。\n"
        "5. 多个不同角色不要合并。\n\n"
        "请返回一个 JSON, 包含 merged 列表, 每项有 canonical_name, aliases 和 merged_indices (输入序号, 从1开始)。\n"
        "如果所有角色都不同，则每个角色单独成组。"
    )

    prompt = (
        "以下是待合并的角色候选列表:\n\n"
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
    candidates: list[CandidateCharacterInput],
    merge_groups: list[dict[str, object]],
) -> list[CandidateCharacterInput]:
    """Given merge groups, produce a deduplicated candidate list.

    For each group:
    - Use canonical_name as the name.
    - Collect all aliases from the group.
    - Merge traits and description from all merged members.
    - Use the first member's role and first_appearance.
    """
    merged: list[CandidateCharacterInput] = []
    seen_indices: set[int] = set()

    for group in merge_groups:
        canonical = str(group["canonical_name"])
        aliases_raw = group.get("aliases", [])
        aliases: list[str] = [str(a) for a in aliases_raw] if isinstance(aliases_raw, list) else []
        indices_raw = group.get("merged_indices", [])
        indices: list[int] = [int(i) for i in indices_raw] if isinstance(indices_raw, list) else []

        merged_traits: list[str] = []
        merged_description_parts: list[str] = []
        first_role = "配角"
        first_appearance = ""

        for idx in indices:
            c_idx = idx - 1  # convert to 0-based
            if c_idx < 0 or c_idx >= len(candidates):
                continue
            seen_indices.add(idx)
            c = candidates[c_idx]

            if not first_role or first_role == "配角":
                first_role = c.role
            if not first_appearance and c.first_appearance:
                first_appearance = c.first_appearance

            for t in c.traits:
                if t not in merged_traits:
                    merged_traits.append(t)
            if c.description:
                merged_description_parts.append(c.description)

        # Also add canonical name and aliases to the alias list
        all_aliases = list(aliases)
        for a in [canonical] + aliases:
            if a and a not in all_aliases:
                all_aliases.append(a)

        merged.append(
            CandidateCharacterInput(
                name=_normalise_name(canonical),
                role=first_role,
                traits=sorted(set(merged_traits)),
                description="; ".join(merged_description_parts),
                first_appearance=first_appearance,
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


async def merge_aliases(
    provider: TextGenerationProvider,
    candidates: list[CandidateCharacterInput],
) -> list[CandidateCharacterInput]:
    """Merge duplicate/alias candidates into a deduplicated list.

    Args:
        provider: An LLM provider for semantic alias resolution.
        candidates: Raw candidate characters from M05.

    Returns:
        A deduplicated list of CandidateCharacterInput.
    """
    if len(candidates) <= 1:
        # Nothing to merge
        return candidates

    # Step 1: Exact-name dedup (deterministic, fast-path)
    name_map: dict[str, CandidateCharacterInput] = {}
    for c in candidates:
        key = _normalise_name(c.name)
        if key in name_map:
            existing = name_map[key]
            # Merge traits
            for t in c.traits:
                if t not in existing.traits:
                    existing.traits.append(t)
            if c.description:
                existing.description = (
                    f"{existing.description}; {c.description}" if existing.description else c.description
                )
            if c.first_appearance and not existing.first_appearance:
                existing.first_appearance = c.first_appearance
            if c.role and existing.role == "配角":
                existing.role = c.role
        else:
            name_map[key] = c

    exact_dedup = list(name_map.values())

    if len(exact_dedup) <= 1:
        return exact_dedup

    # Step 2: LLM-assisted semantic merge
    merge_groups = await _llm_merge_candidates(provider, exact_dedup)

    return _merge_by_indices(exact_dedup, merge_groups)
