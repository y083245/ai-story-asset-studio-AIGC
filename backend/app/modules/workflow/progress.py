"""User-readable progress messages for visual asset workflows."""

from __future__ import annotations

from typing import Any

_STAGE_MESSAGES: dict[str, str] = {
    "parsing_novel": "正在解析小说...",
    "cleaning_text": "正在清洗文本...",
    "detecting_genre": "正在识别风格...",
    "waiting_style_confirmation": "等待用户确认风格...",
    "extracting_characters": "正在提取角色...",
    "extracting_scenes": "正在提取场景...",
    "extracting_props": "正在提取道具...",
    "building_story_bible": "正在整理故事资产设定...",
    "publishing_analysis": "正在发布分析结果...",
    "generating_character_assets": "正在生成角色图片...",
    "generating_scene_assets": "正在生成场景图片...",
    "generating_prop_assets": "正在生成道具图片...",
    "checking_image_quality": "正在检查图片质量...",
    "retrying_failed_images": "正在重试失败图片...",
    "full_generation_starting": "正在启动一键生成...",
    "full_generation_analyze": "第一步：分析小说...",
    "full_generation_asset": "第二步：生成图片资产...",
    "idle": "等待中...",
    "completed": "已完成",
    "failed": "处理失败",
    "cancelled": "已取消",
    "retrying": "正在重试...",
}


def build_progress_message(stage: str, context: dict[str, Any] | None = None) -> str:
    return _STAGE_MESSAGES.get(stage, f"正在处理: {stage}")
