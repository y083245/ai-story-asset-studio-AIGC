"""Fake activity implementations for local testing and demo mode."""

from __future__ import annotations

import uuid
from typing import Any


class FakeNovelIntakeActivity:
    async def parse_novel(self, project_id: str, text: str) -> dict[str, Any]:
        return {
            "novel_id": str(uuid.uuid4()),
            "word_count": len(text),
            "title": "测试小说",
            "raw_text": text or "第一章 测试内容",
        }

    async def clean_text(self, project_id: str, novel_id: str) -> dict[str, Any]:
        return {
            "novel_id": novel_id,
            "cleaned_text": "清洗后的文本内容",
            "chunk_count": 1,
            "chunks": [{"chunk_index": 0, "content": "清洗后的文本内容"}],
        }


class FakeAnalysisActivity:
    async def detect_genre(self, project_id: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "genre": "都市爱情",
            "style_id": "urban_drama",
            "confidence": 0.86,
            "sub_genres": ["职场", "情感"],
            "style_tags": ["现代", "清爽", "写实"],
        }

    async def extract_characters(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "characters": [
                {
                    "character_id": "CH_001",
                    "name": "林晓",
                    "role": "主角",
                    "gender": "女",
                    "age_range": "25岁",
                    "description": "聪明坚定的职场新人",
                    "default_outfit": "白色衬衫搭配深色西装裤",
                },
                {
                    "character_id": "CH_002",
                    "name": "陈宇",
                    "role": "主角",
                    "gender": "男",
                    "age_range": "28岁",
                    "description": "成熟克制的项目负责人",
                    "default_outfit": "深灰色西装外套",
                },
            ]
        }

    async def extract_scenes(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "scenes": [
                {
                    "scene_id": "SC_001",
                    "name": "办公室",
                    "scene_type": "室内",
                    "time_of_day": "白天",
                    "description": "明亮整洁的现代办公室",
                    "fixed_anchors": ["落地窗", "长会议桌", "电脑工位"],
                }
            ]
        }

    async def extract_props(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "props": [
                {
                    "prop_id": "PR_001",
                    "name": "项目文件夹",
                    "category": "办公用品",
                    "visual_features": "深蓝色硬壳文件夹，贴有白色标签",
                    "plot_function": "承载关键项目资料",
                }
            ]
        }

    async def build_story_bible(
        self,
        project_id: str,
        characters: list[dict[str, Any]],
        scenes: list[dict[str, Any]],
        props: list[dict[str, Any]],
        story: dict[str, Any],
        style_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "bible_id": str(uuid.uuid4()),
            "version": 1,
            "genre": style_id or "urban_drama",
            "visual_style": "现代写实，干净光线",
            "story_summary": "人物围绕关键项目资料展开冲突与合作。",
            "characters": characters,
            "scenes": scenes,
            "props": props,
        }


class FakeImageAssetActivity:
    async def generate_character_image(self, project_id: str, character: dict[str, Any], style: str) -> dict[str, Any]:
        return {
            "image_id": str(uuid.uuid4()),
            "type": "character",
            "url": f"https://example.local/assets/{uuid.uuid4()}.png",
            "character_name": character.get("name", ""),
            "style": style,
        }

    async def generate_scene_image(self, project_id: str, scene: dict[str, Any], style: str) -> dict[str, Any]:
        return {
            "image_id": str(uuid.uuid4()),
            "type": "scene",
            "url": f"https://example.local/assets/{uuid.uuid4()}.png",
            "scene_name": scene.get("name", ""),
            "style": style,
        }

    async def generate_prop_image(self, project_id: str, prop: dict[str, Any], style: str) -> dict[str, Any]:
        return {
            "image_id": str(uuid.uuid4()),
            "type": "prop",
            "url": f"https://example.local/assets/{uuid.uuid4()}.png",
            "prop_name": prop.get("name", ""),
            "style": style,
        }


class FakeQualityActivity:
    async def check_image_quality(self, project_id: str, images: dict[str, Any]) -> dict[str, Any]:
        return {"passed": True, "score": 0.92, "issues": [], "image_count": 1}

    async def check_image_quality_failed(self, project_id: str, images: dict[str, Any]) -> dict[str, Any]:
        return {
            "passed": False,
            "score": 0.45,
            "issues": [{"type": "blur", "severity": "high", "description": "图片模糊"}],
            "image_count": 1,
        }

    async def auto_fix_image(self, project_id: str, quality_report: dict[str, Any]) -> dict[str, Any]:
        return {"fixed": True, "fixed_url": f"https://example.local/assets/{uuid.uuid4()}.png"}


def create_default_fake_activities() -> dict[str, Any]:
    novel = FakeNovelIntakeActivity()
    analysis = FakeAnalysisActivity()
    image = FakeImageAssetActivity()
    quality = FakeQualityActivity()
    return {
        "parse_novel": novel.parse_novel,
        "clean_text": novel.clean_text,
        "detect_genre": analysis.detect_genre,
        "extract_characters": analysis.extract_characters,
        "extract_scenes": analysis.extract_scenes,
        "extract_props": analysis.extract_props,
        "build_story_bible": analysis.build_story_bible,
        "generate_character_image": image.generate_character_image,
        "generate_scene_image": image.generate_scene_image,
        "generate_prop_image": image.generate_prop_image,
        "check_image_quality": quality.check_image_quality,
        "check_image_quality_failed": quality.check_image_quality_failed,
        "auto_fix_image": quality.auto_fix_image,
    }
