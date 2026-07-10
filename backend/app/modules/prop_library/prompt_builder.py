"""Prompt builders for the Prop Library module.

Generates:
- prop_prompt: A Chinese-language image generation prompt for the prop
  on a plain white background as a singleton product reference image.
- usage_prompt: A Chinese-language image generation prompt showing the
  prop in use (on set, held, or close-up).
"""

from __future__ import annotations

from app.modules.prop_library.schemas import CandidatePropInput, StateTimelineItem


def build_prop_prompt(
    candidate: CandidatePropInput,
    visual_features: str,
    material: str,
    color: str,
    size: str,
) -> str:
    """Build a singleton prop prompt with plain white background requirement.

    The prompt describes the prop for a clean product-style reference image.
    """
    parts: list[str] = []

    # Core description
    parts.append(f"一件{candidate.name}")

    if material:
        parts.append(f"材质为{material}")
    if color:
        parts.append(f"颜色为{color}")
    if size:
        parts.append(f"尺寸约{size}")

    if visual_features:
        parts.append(visual_features)

    # White background requirement (hard rule)
    parts.append("纯白背景")
    parts.append("正面平视角度")
    parts.append("高清晰度产品级拍摄风格")
    parts.append("无人物无场景无阴影")
    parts.append("柔和均匀的影棚灯光")

    return "，".join(parts) + "。"


def build_usage_prompt(
    candidate: CandidatePropInput,
    timeline: list[StateTimelineItem],
    owner_name: str = "",
    first_appearance: str = "",
) -> str:
    """Build a usage prompt showing the prop in context (held, placed, or close-up).

    The prompt aligns with the state_timeline to show the prop in action.
    """
    if not timeline:
        # Fallback: generic usage prompt
        owner_ref = owner_name if owner_name else "角色"
        return f"{owner_ref}手持{candidate.name}，{candidate.description or candidate.name}细节参考图，质感光影，浅景深。"

    # Use the most visually interesting state entry
    # Prefer states with action keywords
    action_states = ["手持", "佩戴", "使用", "展示", "交给", "拿出"]
    chosen_entry = timeline[0]
    for entry in timeline:
        for kw in action_states:
            if kw in entry.state:
                chosen_entry = entry
                break

    state_text = chosen_entry.state
    state_desc = chosen_entry.description if chosen_entry.description else ""

    parts: list[str] = []

    owner_ref = owner_name if owner_name else "角色"

    if "手持" in state_text or "拿出" in state_text:
        parts.append(f"{owner_ref}手持{candidate.name}")
    elif "佩戴" in state_text:
        parts.append(f"{owner_ref}佩戴{candidate.name}")
    elif "放在" in state_text:
        parts.append(f"{candidate.name}放置在场景中")
    elif "展示" in state_text:
        parts.append(f"{candidate.name}的细节参考图")
    else:
        parts.append(f"{candidate.name}在场景中的状态：{state_text}")

    if state_desc:
        parts.append(state_desc)

    if first_appearance:
        parts.append(f"场景描述：{first_appearance}")

    # Add cinematic quality
    parts.append("质感光影")
    parts.append("浅景深")
    parts.append("高清画质")

    return "，".join(parts) + "。"


def infer_visual_details(
    candidate: CandidatePropInput,
) -> tuple[str, str, str, str]:
    """Infer visual_features, material, color, size from candidate description.

    Uses keyword matching from the candidate's description to fill in
    physical details.
    """
    desc = candidate.description or ""
    name = candidate.name or ""

    # Infer material
    material = ""
    material_map = {
        "银": "银质",
        "金": "金质",
        "铜": "铜质",
        "铁": "铁质",
        "钢": "钢制",
        "木": "木质",
        "皮": "皮革",
        "布": "布料",
        "塑料": "塑料",
        "玻璃": "玻璃",
        "陶瓷": "陶瓷",
        "纸": "纸质",
        "玉": "玉石",
        "石": "石材",
        "水晶": "水晶",
        "钻石": "钻石",
        "宝石": "宝石",
    }
    for kw, mat in material_map.items():
        if kw in name or kw in desc:
            material = mat
            break

    # Infer color
    color = ""
    color_map = {
        "黑色": "黑色",
        "白色": "白色",
        "红色": "红色",
        "蓝色": "蓝色",
        "绿色": "绿色",
        "黄色": "黄色",
        "紫色": "紫色",
        "金色": "金色",
        "银色": "银色",
        "灰色": "灰色",
        "粉色": "粉色",
        "透明": "透明",
    }
    for kw, col in color_map.items():
        if kw in name or kw in desc:
            color = col
            break

    # Infer size
    size = ""
    size_map: dict[str, str] = {
        "戒指": "直径约2厘米",
        "项链": "链长约45厘米",
        "耳环": "长约3厘米",
        "手镯": "直径约7厘米",
        "手机": "约15x7厘米",
        "文件": "A4尺寸",
        "合同": "A4尺寸",
        "书": "约20x14厘米",
        "笔": "长约14厘米",
        "刀": "刃长约15厘米",
        "剑": "长约90厘米",
        "杯子": "高约10厘米",
        "钥匙": "长约6厘米",
        "钱包": "约12x9厘米",
        "照片": "约15x10厘米",
        "盒子": "约20x15x10厘米",
        "手表": "表盘直径约4厘米",
    }
    for kw, sz in size_map.items():
        if kw in name or kw in desc:
            size = sz
            break

    # Build visual_features from description
    visual_features = candidate.description if candidate.description else ""

    return visual_features, material, color, size


def classify_importance(candidate: CandidatePropInput) -> str:
    """Classify a prop's importance based on description and function hints.

    Returns one of: "core", "supporting", "minor"
    """
    desc = candidate.description or ""
    func = candidate.function_hint or ""
    combined = desc + func

    # Core indicators: key plot device, drives story, appears multiple times
    core_keywords = ["关键证据", "关键信物", "核心道具", "推动剧情"]
    # Check for "核心" but NOT "非核心"
    if "核心" in combined and "非核心" not in combined:
        core_score = 1
    else:
        core_score = sum(1 for kw in core_keywords if kw in combined)
    supporting_keywords = ["常用", "随身", "反复出现", "标志性", "象征"]
    minor_keywords = ["装饰", "背景", "一次性", "非核心", "仅出现一次"]

    supporting_score = sum(1 for kw in supporting_keywords if kw in combined)
    minor_score = sum(1 for kw in minor_keywords if kw in combined)

    if core_score > 0:
        return "core"
    if supporting_score > 0:
        return "supporting"
    if minor_score > 0:
        return "minor"

    # Default: if prop has aliases suggesting it's referenced multiple ways, it's at least supporting
    if candidate.aliases and len(candidate.aliases) >= 2:
        return "supporting"

    # If short description with no function hint, it's minor
    if len(desc) < 20 and not func:
        return "minor"

    return "supporting"
