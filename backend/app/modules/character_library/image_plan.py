"""Reference-image plan generation for the Character Library module.

Generates a list of reference-image plan items that the M11 Image Asset
module will use to produce character reference assets.

Rules:
- Protagonist (主角): minimum 5 categories, all priority "required".
- Supporting (配角): 2-3 categories, some optional.
- Other (反派/路人): at least 1 category.
"""

from __future__ import annotations

from typing import Any

from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest

# ---------------------------------------------------------------------------
# Default plans by role type
# ---------------------------------------------------------------------------

_DEFAULT_PLAN_LEAD: list[dict[str, str]] = [
    {
        "category": "正面半身",
        "description": "正面半身像，中性表情，展示完整正面外貌",
        "priority": "required",
    },
    {
        "category": "三分之二侧脸",
        "description": "3/4左侧脸，展示侧脸轮廓和五官立体感",
        "priority": "required",
    },
    {
        "category": "全身站姿",
        "description": "正面全身站立，展示全身比例和服装",
        "priority": "required",
    },
    {
        "category": "表情九宫格",
        "description": "喜怒哀乐惊讶厌恶鄙视冷漠专注9种表情",
        "priority": "required",
    },
    {
        "category": "服装设定",
        "description": "正面背面服装三视图，展示服装细节",
        "priority": "required",
    },
]

_DEFAULT_PLAN_SUPPORTING: list[dict[str, str]] = [
    {
        "category": "正面半身",
        "description": "正面半身像，中性表情",
        "priority": "required",
    },
    {
        "category": "全身站姿",
        "description": "正面全身站立，展示服装",
        "priority": "required",
    },
    {
        "category": "表情集",
        "description": "3-5种关键表情",
        "priority": "optional",
    },
]

_DEFAULT_PLAN_OTHER: list[dict[str, str]] = [
    {
        "category": "正面半身",
        "description": "正面半身像，展示基本外貌特征",
        "priority": "required",
    },
]


def _get_default_plan(role_type: str) -> list[dict[str, str]]:
    """Return a default reference image plan based on role type."""
    role_lower = role_type.lower()
    if "主角" in role_lower or "lead" in role_lower or "protagonist" in role_lower:
        return [dict(d) for d in _DEFAULT_PLAN_LEAD]
    elif "配角" in role_lower or "support" in role_lower:
        return [dict(d) for d in _DEFAULT_PLAN_SUPPORTING]
    else:
        return [dict(d) for d in _DEFAULT_PLAN_OTHER]


# ---------------------------------------------------------------------------
# Deterministic plan enrichment
# ---------------------------------------------------------------------------


def _enrich_plan_descriptions(plan: list[dict[str, str]], profile: dict[str, Any]) -> list[dict[str, str]]:
    """Append character-specific details to plan item descriptions."""
    name = profile.get("name", "")
    outfit = profile.get("default_outfit", "")
    personality = profile.get("personality", "")

    enriched: list[dict[str, str]] = []
    for item in plan:
        desc = item["description"]
        if name and "正面" in item["category"] and name not in desc:
            desc = f"{desc}，角色 {name}"
        if outfit and "服装" in item["category"] and outfit not in desc:
            desc = f"{desc}，{outfit}"
        if personality and "表情" in item["category"]:
            desc = f"{desc}，体现{personality}气质"
        enriched.append({**item, "description": desc})

    return enriched


# ---------------------------------------------------------------------------
# LLM-assisted plan generation
# ---------------------------------------------------------------------------


async def _llm_plan(
    provider: TextGenerationProvider,
    profile: dict[str, Any],
    role_type: str,
    default_plan: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Use LLM to generate a tailored reference image plan."""
    import json as _json

    system_prompt = (
        "你是一个角色参考图规划助手。请根据角色信息生成 reference_image_plan。\n"
        "每项包含 category (类别), description (详细prompt描述), priority (required/optional)。\n"
        "主角至少5类(正面半身、三分之二侧脸、全身站姿、表情九宫格、服装设定)，全部 required。\n"
        "配角2-3类。\n"
        '返回 JSON: {"plan": [{...}, ...]}'
    )

    prompt = (
        f"角色信息:\n{_json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        f"角色定位: {role_type}\n\n"
        f"默认计划 (供参考):\n{_json.dumps(default_plan, ensure_ascii=False, indent=2)}\n\n"
        "请生成最适合该角色的参考图计划。"
    )

    try:
        request = TextGenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=2048,
            timeout_seconds=30,
        )
        response = await provider.generate_json(request)

        if response.json_data and "plan" in response.json_data:
            plan = response.json_data["plan"]
            if isinstance(plan, list) and len(plan) > 0:
                return [
                    {
                        "category": str(item.get("category", "")),
                        "description": str(item.get("description", "")),
                        "priority": str(item.get("priority", "required")),
                    }
                    for item in plan
                    if isinstance(item, dict) and item.get("category")
                ]
    except Exception:
        pass

    return default_plan


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_image_plan(
    provider: TextGenerationProvider,
    profile: dict[str, Any],
    role_type: str = "配角",
    use_llm: bool = True,
) -> list[dict[str, str]]:
    """Generate a reference image plan for a character.

    Args:
        provider: LLM provider for plan generation.
        profile: Character profile dict.
        role_type: Character role (主角/配角/反派/路人).
        use_llm: Whether to use LLM for plan generation.

    Returns:
        A list of plan items, each with category, description, priority.
    """
    default_plan = _get_default_plan(role_type)
    enriched_default = _enrich_plan_descriptions(default_plan, profile)

    if use_llm:
        return await _llm_plan(provider, profile, role_type, enriched_default)

    return enriched_default
