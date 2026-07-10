"""Fixed anchor generation and validation for the Scene Library module.

Fixed anchors are stationary visual elements within a scene that remain
consistent across different composition views. They serve as visual "anchors"
that allow the audience to recognize the same space even when the composition
position changes.

Rules:
- Every scene MUST have at least 3 fixed_anchors.
- Anchors describe fixed, permanent elements (e.g. "红木办公桌", "落地窗", "书架").
- Anchors must NOT include characters, movable props, or transient effects.
- Anchors are validated for quality (specificity, non-redundancy).
"""

from __future__ import annotations

from typing import Any

from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest
from app.modules.scene_library.schemas import CandidateSceneInput

# ---------------------------------------------------------------------------
# Deterministic anchor extraction from candidate data
# ---------------------------------------------------------------------------


def extract_anchors_from_candidate(candidate: CandidateSceneInput) -> list[str]:
    """Extract anchor elements from a candidate scene's anchors and description.

    This is a deterministic fallback that uses existing anchor keywords
    and supplements with spatial reasoning from the description.
    """
    anchors: list[str] = list(candidate.anchors) if candidate.anchors else []

    # Parse description for spatial keywords and generate anchors
    spatial_keywords = {
        "窗": "窗户",
        "门": "门",
        "桌": "桌子",
        "椅": "椅子",
        "灯": "灯具",
        "沙发": "沙发",
        "书架": "书架",
        "床": "床",
        "柜": "柜子",
        "楼梯": "楼梯",
        "吧台": "吧台",
        "台": "台面",
        "墙": "墙面",
        "地板": "地板",
        "天花板": "天花板",
        "柱": "柱子",
        "镜": "镜子",
        "帘": "窗帘",
        "屏风": "屏风",
        "壁炉": "壁炉",
        "画": "挂画",
        "电视": "电视墙",
    }

    desc = candidate.description
    for keyword, anchor_name in spatial_keywords.items():
        if keyword in desc and anchor_name not in anchors:
            anchors.append(anchor_name)

    return anchors


# ---------------------------------------------------------------------------
# Deterministic anchor quality checks
# ---------------------------------------------------------------------------


def validate_anchors(anchors: list[str]) -> list[str]:
    """Validate a list of anchors against quality rules.

    Returns a list of validation error messages (empty = valid).
    """
    errors: list[str] = []

    # Rule 1: At least 3 anchors
    if len(anchors) < 3:
        errors.append(f"固定锚点不足：需要至少3个，当前{len(anchors)}个")

    # Rule 2: No empty or whitespace-only anchors
    non_empty = [a for a in anchors if a and a.strip()]
    if len(non_empty) != len(anchors):
        errors.append("固定锚点不能为空")

    # Rule 3: No duplicate anchors (case-insensitive)
    lower_anchors = [a.strip().lower() for a in non_empty]
    if len(set(lower_anchors)) != len(lower_anchors):
        errors.append("固定锚点不能重复")

    # Rule 4: Anchors must not be generic single characters
    if any(len(a.strip()) <= 1 for a in non_empty):
        errors.append("固定锚点名称不能为单个字符")

    # Rule 5: Anchors should not reference people
    people_keywords = ["人", "角色", "男主", "女主", "演员", "他", "她"]
    for a in non_empty:
        if any(kw in a for kw in people_keywords):
            errors.append(f'固定锚点不能涉及人物: "{a}"')

    return errors


# ---------------------------------------------------------------------------
# LLM-assisted anchor generation
# ---------------------------------------------------------------------------


async def generate_anchors_with_llm(
    provider: TextGenerationProvider,
    scene_name: str,
    scene_description: str,
    existing_anchors: list[str],
) -> list[str]:
    """Use LLM to generate a complete set of fixed anchors for a scene.

    Falls back to deterministic anchors + defaults if LLM fails.
    """
    import json as _json

    system_prompt = (
        "你是一个场景固定锚点生成助手。固定锚点是场景中固定不动的视觉元素，"
        "用于确保不同构图视角中场景的一致性和可识别性。\n\n"
        "规则:\n"
        "1. 每个场景至少3个固定锚点，建议4-6个。\n"
        "2. 锚点必须是固定元素（如「红木办公桌」「落地窗」「书架」），不是人物或可移动道具。\n"
        "3. 锚点应该具体且具有辨识度（不要只写「桌子」，要写「红木办公桌」）。\n"
        "4. 锚点应分布在前景、中景、背景不同空间层。\n"
        '5. 返回 JSON: {"anchors": ["锚点1", "锚点2", ...]}'
    )

    prompt = (
        f"场景名称: {scene_name}\n"
        f"场景描述: {scene_description}\n"
        f"已有的锚点参考: {_json.dumps(existing_anchors, ensure_ascii=False)}\n\n"
        "请为这个场景生成充分的固定锚点列表（至少3个，建议4-6个）。"
    )

    try:
        request = TextGenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=1024,
            timeout_seconds=30,
        )
        response = await provider.generate_json(request)

        if response.json_data and "anchors" in response.json_data:
            llm_anchors = response.json_data["anchors"]
            if isinstance(llm_anchors, list) and len(llm_anchors) >= 3:
                return [str(a) for a in llm_anchors]
    except Exception:
        pass

    # Fallback: use existing anchors, padded with defaults if needed
    anchors = list(existing_anchors)
    defaults = [
        "主光源",
        "地板纹理",
        "墙面装饰",
        "天花板",
        "主要家具",
    ]
    for d in defaults:
        if len(anchors) >= 3:
            break
        if d not in anchors:
            anchors.append(d)

    return anchors


# ---------------------------------------------------------------------------
# Spatial layering extraction
# ---------------------------------------------------------------------------


def extract_spatial_elements(
    scene_name: str,
    scene_description: str,
    anchors: list[str],
) -> dict[str, list[str]]:
    """Distribute scene elements into foreground, midground, and background layers.

    Returns a dict with keys: foreground_elements, midground_elements, background_elements.
    """
    foreground: list[str] = []
    midground: list[str] = []
    background: list[str] = []

    # Midground: the anchors themselves (core scene structure)
    midground = list(anchors)

    # Foreground signals: close-up items
    fg_keywords: dict[str, str] = {
        "杯": "杯子",
        "笔": "文具",
        "文件": "文件纸张",
        "手机": "手机",
        "书": "书籍",
        "花": "花瓶/花束",
        "咖啡": "咖啡杯",
        "茶": "茶具",
        "电脑": "笔记本电脑",
        "键盘": "键盘",
        "烟灰缸": "烟灰缸",
        "杂志": "杂志",
        "遥控器": "遥控器",
        "眼镜": "眼镜",
        "钥匙": "钥匙",
        "餐盘": "餐具",
        "食物": "食物",
    }

    # Background signals: distant elements
    bg_keywords: dict[str, str] = {
        "窗外": "窗外景色",
        "城市": "城市天际线",
        "天空": "天空",
        "云": "云层",
        "山": "远山",
        "海": "海面",
        "街道": "街道远景",
        "高楼": "远处高楼",
        "树": "树木",
        "花园": "花园",
        "远": "远景",
        "地平线": "地平线",
    }

    desc = scene_description.lower() + scene_name.lower()
    for keyword, element in fg_keywords.items():
        if keyword in desc and element not in foreground:
            foreground.append(element)
    for keyword, element in bg_keywords.items():
        if keyword in desc and element not in background:
            background.append(element)

    # Ensure at least some elements in each layer
    if not foreground:
        foreground = ["近景摆设"]
    if not midground:
        midground = ["主要空间结构"]
    if not background:
        background = ["远景/环境背景"]

    return {
        "foreground_elements": foreground,
        "midground_elements": midground,
        "background_elements": background,
    }


# ---------------------------------------------------------------------------
# Composition view generation
# ---------------------------------------------------------------------------


def generate_composition_views(scene_name: str, scene_description: str, scene_type: str = "室内") -> list[str]:
    """Generate allowed composition views for a scene.

    Interior scenes favor clear mid-distance and detail views.
    Exterior scenes favor wide establishing and layered space views.
    """
    is_exterior = "室外" in scene_type or "户外" in scene_type or "街上" in scene_name

    if is_exterior:
        return [
            "远景广角构图",
            "中景平视构图",
            "低角度仰视构图",
            "高角度俯视构图",
            "全景横向构图",
        ]

    return [
        "中景平视构图",
        "近景细节构图",
        "门框或窗框前景构图",
        "室内广角构图",
        "侧向空间层次构图",
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def ensure_anchors_and_enrich(
    provider: TextGenerationProvider,
    candidate: CandidateSceneInput,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Generate and validate anchors, plus all derived spatial/composition info.

    Args:
        provider: LLM provider for optional anchor generation.
        candidate: A single merged scene candidate.
        use_llm: Whether to use LLM for anchor generation.

    Returns:
        A dict with: fixed_anchors, foreground_elements, midground_elements,
        background_elements, composition_views.
    """
    # Step 1: Extract raw anchors from candidate
    raw_anchors = extract_anchors_from_candidate(candidate)

    # Step 2: LLM-assisted anchor generation (or fallback)
    if use_llm and len(raw_anchors) < 3:
        anchors = await generate_anchors_with_llm(
            provider,
            candidate.name,
            candidate.description,
            raw_anchors,
        )
    else:
        anchors = raw_anchors

    # Step 3: Ensure minimum 3 anchors
    defaults = [
        f"{candidate.name}的主结构",
        "主光源方向",
        "地面材质",
    ]
    for d in defaults:
        if len(anchors) >= 3:
            break
        if d not in anchors:
            anchors.append(d)

    # Step 4: Deduplicate and clean
    seen: set[str] = set()
    cleaned: list[str] = []
    for a in anchors:
        a_clean = a.strip()
        if a_clean and a_clean.lower() not in seen:
            seen.add(a_clean.lower())
            cleaned.append(a_clean)
    anchors = cleaned

    # Ensure at least 3
    while len(anchors) < 3:
        anchors.append("场景基本结构")

    # Step 5: Generate spatial layering
    layers = extract_spatial_elements(candidate.name, candidate.description, anchors)

    # Step 6: Generate composition views
    scene_type = (
        "室外"
        if any(
            kw in candidate.name + candidate.description
            for kw in ["街道", "公园", "广场", "户外", "花园", "天台", "海边", "野外"]
        )
        else "室内"
    )
    composition_angles = generate_composition_views(candidate.name, candidate.description, scene_type)

    return {
        "fixed_anchors": anchors,
        "foreground_elements": layers["foreground_elements"],
        "midground_elements": layers["midground_elements"],
        "background_elements": layers["background_elements"],
        "composition_views": composition_angles,
    }
