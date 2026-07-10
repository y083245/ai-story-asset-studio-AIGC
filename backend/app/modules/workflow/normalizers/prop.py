"""Prop-extractor output normalizer."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.modules.template_style.style_alias import DEFAULT_STYLE_ID
from app.modules.workflow.normalizers.common import as_list, dict_of, field, string_list


def normalize_props(items: list[Any], *, style_id: str = DEFAULT_STYLE_ID) -> list[dict[str, Any]]:  # noqa: ARG001
    result: list[dict[str, Any]] = []
    for index, value in enumerate(items, 1):
        item = dict_of(value)
        name = str(item.get("name") or f"道具{index}")
        visual_features = str(item.get("visual_features") or item.get("description") or "")
        prop_prompt = str(item.get("prop_prompt") or "")
        if settings.prompt_engine_mode == "legacy":
            prop_prompt = _ensure_prop_prompt(
                prop_prompt,
                name=name,
                visual_features=visual_features,
                material=str(item.get("material") or ""),
                color=str(item.get("color") or ""),
                size=str(item.get("size") or ""),
                two_d=str(item.get("two_d_image_prompt") or item.get("two_d_prompt") or ""),
                three_d=str(item.get("three_d_image_prompt") or item.get("three_d_prompt") or ""),
                realistic=str(item.get("realistic_image_prompt") or item.get("realistic_prompt") or ""),
            )
            needs_synthesis = None
        else:
            needs_synthesis = not _has_complete_prop_prompt_labels(prop_prompt)
        result.append(
            {
                "prop_id": str(item.get("prop_id") or f"PR_{index:03d}"),
                "name": name,
                "aliases": string_list(item.get("aliases")),
                "category": str(item.get("category") or item.get("type") or ""),
                "importance": str(item.get("importance") or ""),
                "owner_name": str(item.get("owner_name") or ""),
                "visual_features": visual_features,
                "material": str(item.get("material") or ""),
                "color": str(item.get("color") or ""),
                "size": str(item.get("size") or ""),
                "first_appearance": str(item.get("first_appearance") or ""),
                "plot_function": str(item.get("plot_function") or item.get("function") or ""),
                "state_timeline": _normalize_state_timeline(item.get("state_timeline")),
                "prop_prompt": prop_prompt,
                **({} if needs_synthesis is None else {"prop_prompt_needs_synthesis": needs_synthesis}),
                "two_d_image_prompt": _extract_labeled_prompt(prop_prompt, "2D 动漫风绘图提示词")
                or str(item.get("two_d_image_prompt") or item.get("two_d_prompt") or ""),
                "three_d_image_prompt": _extract_labeled_prompt(prop_prompt, "3D 动漫风绘图提示词")
                or str(item.get("three_d_image_prompt") or item.get("three_d_prompt") or ""),
                "realistic_image_prompt": _extract_labeled_prompt(prop_prompt, "写实漫剧风绘图提示词")
                or str(item.get("realistic_image_prompt") or item.get("realistic_prompt") or ""),
                "usage_prompt": str(item.get("usage_prompt") or _default_usage_prompt(name, visual_features)),
            }
        )
    return result


# ── helpers ──────────────────────────────────────────────────────────


def _has_complete_prop_prompt_labels(prompt: str) -> bool:
    labels = ("【2D 动漫风绘图提示词】", "【3D 动漫风绘图提示词】", "【写实漫剧风绘图提示词】")
    return all(_extract_labeled_prompt(prompt, label.strip("【】")) for label in labels)


def _ensure_prop_prompt(
    prompt: str,
    *,
    name: str,
    visual_features: str,
    material: str,
    color: str,
    size: str,
    two_d: str,
    three_d: str,
    realistic: str,
) -> str:
    text = prompt.strip()
    if all(label in text for label in ("【2D 动漫风绘图提示词】", "【3D 动漫风绘图提示词】", "【写实漫剧风绘图提示词】")):
        return _ensure_prop_white_background(text)

    description = "，".join(
        value
        for value in [
            visual_features or name,
            field("材质", material),
            field("颜色", color),
            field("尺寸", size),
        ]
        if value
    )
    two_d_prompt = two_d or f"{name}，{description}，纯白背景，线条清楚，色彩明确，适合短视频封面和分镜参考。"
    three_d_prompt = three_d or f"{name}，{description}，纯白背景，3D建模参考，材质清楚，光影层次明确。"
    realistic_prompt = realistic or f"{name}，{description}，纯白背景，写实漫剧质感，真实纹理，细节清楚。"
    return _ensure_prop_white_background(
        f"【标准名称】：{name}"
        f"【原文出处 & 详细描述】：{description}"
        f"【2D 动漫风绘图提示词】：{two_d_prompt}"
        f"【3D 动漫风绘图提示词】：{three_d_prompt}"
        f"【写实漫剧风绘图提示词】：{realistic_prompt}"
    )


def _ensure_prop_white_background(prompt: str) -> str:
    labels = ("【2D 动漫风绘图提示词】", "【3D 动漫风绘图提示词】", "【写实漫剧风绘图提示词】")
    text = prompt
    for label in labels:
        start = text.find(label)
        if start < 0:
            continue
        next_starts = [text.find(next_label, start + len(label)) for next_label in labels if next_label != label]
        next_starts = [index for index in next_starts if index > start]
        end = min(next_starts) if next_starts else len(text)
        section = text[start:end]
        if "纯白背景" not in section:
            text = text[:end].rstrip("。；;，, ") + "，纯白背景。" + text[end:]
    return text


def _extract_labeled_prompt(prompt: str, label: str) -> str:
    start_marker = f"【{label}】："
    start = prompt.find(start_marker)
    if start < 0:
        return ""
    start += len(start_marker)
    end = len(prompt)
    for next_label in ("【2D 动漫风绘图提示词】", "【3D 动漫风绘图提示词】", "【写实漫剧风绘图提示词】"):
        index = prompt.find(next_label, start)
        if index >= 0:
            end = min(end, index)
    return prompt[start:end].strip().strip("。；;，, ").strip()


def _default_usage_prompt(name: str, visual_features: str) -> str:
    return f"{name}在剧情场景中的摆放、手持或特写使用参考图，{visual_features or name}，质感光影，高清细节。"


def _normalize_state_timeline(value: Any) -> list[dict[str, object]]:
    timeline: list[dict[str, object]] = []
    for index, raw_item in enumerate(as_list(value), start=1):
        if isinstance(raw_item, dict):
            state = str(raw_item.get("state") or raw_item.get("description") or "").strip()
            description = str(raw_item.get("description") or state).strip()
            try:
                step_index = int(raw_item.get("step_index") or raw_item.get("step") or index)
            except (TypeError, ValueError):
                step_index = index
            if state or description:
                timeline.append(
                    {
                        "step_index": max(step_index, 1),
                        "state": state or description,
                        "description": description or state,
                    }
                )
            continue

        text = str(raw_item or "").strip()
        if text:
            timeline.append({"step_index": index, "state": text, "description": text})
    return timeline


_as_list = as_list

__all__ = ["normalize_props"]
