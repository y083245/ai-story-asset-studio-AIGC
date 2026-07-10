"""Activity interfaces for the visual asset workflow."""

from __future__ import annotations

from typing import Any, Protocol


class ParseNovelActivity(Protocol):
    async def parse_novel(self, project_id: str, text: str) -> dict[str, Any]: ...


class CleanTextActivity(Protocol):
    async def clean_text(self, project_id: str, novel_id: str) -> dict[str, Any]: ...


class DetectGenreActivity(Protocol):
    async def detect_genre(self, project_id: str, chunks: list[dict[str, Any]]) -> dict[str, Any]: ...


class ExtractCharactersActivity(Protocol):
    async def extract_characters(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]: ...


class ExtractScenesActivity(Protocol):
    async def extract_scenes(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]: ...


class ExtractPropsActivity(Protocol):
    async def extract_props(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]: ...


class BuildStoryBibleActivity(Protocol):
    async def build_story_bible(
        self,
        project_id: str,
        characters: list[dict[str, Any]],
        scenes: list[dict[str, Any]],
        props: list[dict[str, Any]],
        story: dict[str, Any],
        style_id: str | None = None,
    ) -> dict[str, Any]: ...


class GenerateCharacterImageActivity(Protocol):
    async def generate_character_image(
        self, project_id: str, character: dict[str, Any], style: str
    ) -> dict[str, Any]: ...


class GenerateSceneImageActivity(Protocol):
    async def generate_scene_image(self, project_id: str, scene: dict[str, Any], style: str) -> dict[str, Any]: ...


class GeneratePropImageActivity(Protocol):
    async def generate_prop_image(self, project_id: str, prop: dict[str, Any], style: str) -> dict[str, Any]: ...


class CheckImageQualityActivity(Protocol):
    async def check_image_quality(self, project_id: str, images: dict[str, Any]) -> dict[str, Any]: ...


class AutoFixImageActivity(Protocol):
    async def auto_fix_image(self, project_id: str, quality_report: dict[str, Any]) -> dict[str, Any]: ...
