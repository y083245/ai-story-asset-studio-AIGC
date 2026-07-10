"""Analysis workflow activities backed by the configured text provider.

Only orchestrates activity execution and stage-chunk caching.  The pure
data transforms live in :mod:`app.modules.workflow.normalizers` and
:mod:`app.modules.workflow.prompt_render`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from typing import Any

from app.config import settings
from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode
from app.modules.provider_adapter.registry import ProviderRegistry
from app.modules.template_style.story_engine_docs import StoryEngineTemplateRegistry
from app.modules.template_style.style_alias import STYLE_ID_ALIASES  # noqa: F401  # re-exported
from app.modules.template_style.style_alias import normalize_style_id as _normalize_style_id
from app.modules.template_style.style_pack import StylePackRegistry, StylePackTemplate
from app.modules.workflow.normalizers import (
    normalize_characters as _normalize_characters,
)
from app.modules.workflow.normalizers import (
    normalize_genre as _normalize_genre,
)
from app.modules.workflow.normalizers import (
    normalize_props as _normalize_props,
)
from app.modules.workflow.normalizers import (
    normalize_scenes as _normalize_scenes,
)
from app.modules.workflow.normalizers.common import as_list as _as_list
from app.modules.workflow.normalizers.common import dict_of as _dict
from app.modules.workflow.normalizers.common import string_list as _string_list
from app.modules.workflow.prompt_render import render_prompt as _render_prompt
from app.modules.workflow.prompt_render import render_system_prompt as _render_system_prompt
from app.modules.workflow.stage_chunk_cache import (
    load_stage_chunk_success,
    save_stage_chunk_failure,
    save_stage_chunk_success,
)

logger = logging.getLogger("storyasset.analysis")

ASSET_MODULE_IDS = {"genre_detector", "character_extractor", "scene_extractor", "prop_extractor"}


class DeepSeekAnalysisActivities:
    """Run asset-only text analysis through style-pack templates.

    Instance state (``_raw_text_by_project`` etc.) is **per-workflow-run**:
    a fresh instance is constructed by :func:`create_analysis_activities`
    for each analyze workflow, so these dictionaries carry data between
    activities of the same run only.  They are NOT a cross-request cache.

    The provider is fetched lazily via :meth:`_get_provider` on every call
    so provider config changes made through the UI take effect without a
    server restart.
    """

    def __init__(self, provider: TextGenerationProvider | None = None) -> None:
        self._provider = provider  # kept for backwards compat, prefer _get_provider()
        self._raw_text_by_project: dict[str, str] = {}
        self._novel_id_by_project: dict[str, str] = {}
        self._genre_by_project: dict[str, dict[str, Any]] = {}
        self._stage_by_project: dict[str, dict[str, Any]] = {}
        self._style_registry = StylePackRegistry()
        self._style_registry.load_all()
        self._story_engine_docs = StoryEngineTemplateRegistry()

    def _get_provider(self) -> TextGenerationProvider:
        if self._provider is not None:
            return self._provider
        return ProviderRegistry().get_text_generator()

    async def parse_novel(self, project_id: str, text: str) -> dict[str, Any]:
        novel_id = str(uuid.uuid4())
        self._raw_text_by_project[project_id] = text
        self._novel_id_by_project[project_id] = novel_id
        return {"novel_id": novel_id, "word_count": len(text), "title": _title_from_text(text), "raw_text": text}

    async def clean_text(self, project_id: str, novel_id: str) -> dict[str, Any]:  # noqa: ARG002
        text = _clean_text(self._raw_text_by_project.get(project_id, ""))
        chunks = [{"chunk_index": index, "content": chunk} for index, chunk in enumerate(_chunks(text))]
        return {
            "novel_id": self._novel_id_by_project.get(project_id, novel_id),
            "cleaned_text": text,
            "chunk_count": len(chunks),
            "chunks": chunks,
        }

    async def detect_genre(self, project_id: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:  # noqa: ARG002
        cached = self._genre_by_project.get(project_id)
        if cached is not None:
            return cached
        text = self._raw_text_by_project.get(project_id, "")
        template = self._style_registry.get_template("cinematic_realistic", "genre_detector")
        result = await self._run_template(
            project_id,
            "genre_detector",
            "cinematic_realistic",
            template,
            text[:10000],
            template_contract=self._story_engine_docs.get_style_catalog(),
        )
        genre = _normalize_genre(result)
        self._genre_by_project[project_id] = genre
        return genre

    async def extract_characters(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]:  # noqa: ARG002
        resolved_style_id = _normalize_style_id(style_id or str((await self.detect_genre(project_id, [])).get("style_id")))
        stage = await self._ensure_stage(project_id, "character_extractor", style_id=resolved_style_id)
        return {"characters": _normalize_characters(_as_list(stage.get("characters")), style_id=resolved_style_id)}

    async def extract_scenes(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]:  # noqa: ARG002
        resolved_style_id = _normalize_style_id(style_id or str((await self.detect_genre(project_id, [])).get("style_id")))
        stage = await self._ensure_stage(project_id, "scene_extractor", style_id=resolved_style_id)
        return {"scenes": _normalize_scenes(_as_list(stage.get("scenes")), style_id=resolved_style_id)}

    async def extract_props(
        self, project_id: str, story: dict[str, Any], style_id: str | None = None
    ) -> dict[str, Any]:  # noqa: ARG002
        resolved_style_id = _normalize_style_id(style_id or str((await self.detect_genre(project_id, [])).get("style_id")))
        stage = await self._ensure_stage(project_id, "prop_extractor", style_id=resolved_style_id)
        return {"props": _normalize_props(_as_list(stage.get("props")), style_id=resolved_style_id)}

    async def build_story_bible(
        self,
        project_id: str,
        characters: list[dict[str, Any]],
        scenes: list[dict[str, Any]],
        props: list[dict[str, Any]],
        story: dict[str, Any],
        style_id: str | None = None,
    ) -> dict[str, Any]:  # noqa: ARG002
        genre = await self.detect_genre(project_id, [])
        resolved_style_id = _normalize_style_id(style_id or str(genre.get("style_id") or "cinematic_realistic"))
        return {
            "bible_id": f"SB_{uuid.uuid4().hex[:8]}",
            "version": 1,
            "genre": genre.get("genre") or resolved_style_id,
            "style_id": resolved_style_id,
            "visual_style": " / ".join(_string_list(genre.get("style_tags"))) or resolved_style_id,
            "story_summary": (self._raw_text_by_project.get(project_id, "")[:300] or "故事分析已完成"),
            "characters": characters,
            "scenes": scenes,
            "props": props,
        }

    def as_activity_map(self) -> dict[str, Any]:
        return {
            "parse_novel": self.parse_novel,
            "clean_text": self.clean_text,
            "detect_genre": self.detect_genre,
            "extract_characters": self.extract_characters,
            "extract_scenes": self.extract_scenes,
            "extract_props": self.extract_props,
            "build_story_bible": self.build_story_bible,
        }

    async def _ensure_stage(self, project_id: str, module_id: str, *, style_id: str | None = None) -> dict[str, Any]:
        if module_id not in ASSET_MODULE_IDS:
            raise ValueError(f"Unsupported analysis module: {module_id}")
        resolved_style_id = _normalize_style_id(style_id or str((await self.detect_genre(project_id, [])).get("style_id")))
        cache_key = f"{resolved_style_id}:{module_id}"
        project_cache = self._stage_by_project.setdefault(project_id, {})
        if cache_key in project_cache:
            return _dict(project_cache[cache_key])
        template = self._style_registry.get_template(resolved_style_id, module_id)
        template_contract = self._story_engine_docs.get_contract(resolved_style_id, module_id).content
        text = self._raw_text_by_project.get(project_id, "")
        chunks = _chunks(text)
        semaphore = asyncio.Semaphore(max(1, settings.analysis_chunk_concurrency))

        async def process_chunk(index: int, chunk: str) -> dict[str, Any]:
            chunk_hash = _hash_payload(resolved_style_id, module_id, template, chunk, template_contract)
            cached = None
            if settings.analysis_chunk_result_cache:
                cached = await load_stage_chunk_success(
                    project_id=project_id,
                    style_id=resolved_style_id,
                    module_id=module_id,
                    chunk_hash=chunk_hash,
                )
            if isinstance(cached, dict):
                return cached
            try:
                async with semaphore:
                    result = await self._run_template(
                        project_id,
                        module_id,
                        resolved_style_id,
                        template,
                        chunk,
                        template_contract=template_contract,
                    )
            except BaseException as exc:
                await save_stage_chunk_failure(
                    project_id=project_id,
                    style_id=resolved_style_id,
                    module_id=module_id,
                    model_tier=_module_model_tier(module_id),
                    chunk_index=index + 1,
                    chunk_hash=chunk_hash,
                    error=str(exc),
                    attempt=1,
                )
                raise
            await save_stage_chunk_success(
                project_id=project_id,
                style_id=resolved_style_id,
                module_id=module_id,
                model_tier=_module_model_tier(module_id),
                chunk_index=index + 1,
                chunk_hash=chunk_hash,
                result=result,
                attempt=1,
            )
            return result

        results = await asyncio.gather(*(process_chunk(index, chunk) for index, chunk in enumerate(chunks)))
        merged = _merge_stage_results(module_id, results)
        project_cache[cache_key] = merged
        return merged

    async def _run_template(
        self,
        project_id: str,
        module_id: str,
        style_id: str,
        template: StylePackTemplate,
        text: str,
        *,
        template_contract: str | None = None,
    ) -> dict[str, Any]:
        prompt = _render_prompt(
            template,
            text=text,
            context={"style_id": style_id},
            template_contract=template_contract,
        )
        response = await _generate_json_with_hard_timeout(
            self._get_provider(),
            TextGenerationRequest(
                system_prompt=_render_system_prompt(template),
                prompt=prompt,
                temperature=0.2,
                max_tokens=_module_max_tokens(module_id),
                timeout_seconds=_module_timeout(module_id),
                thinking=_module_thinking(module_id),
                user_id=_provider_user_id(project_id),
                metadata={"project_id": project_id, "module_id": module_id, "style_id": style_id},
            ),
            module_id=module_id,
        )
        if not isinstance(response.json_data, dict):
            raise ValueError(f"DeepSeek did not return a JSON object for {module_id}")
        return response.json_data


def create_analysis_activities() -> dict[str, Any]:
    if settings.provider_mode == "fake":
        from app.modules.workflow.fake_activities import create_default_fake_activities

        return create_default_fake_activities()
    return DeepSeekAnalysisActivities().as_activity_map()


# ── low-level plumbing ───────────────────────────────────────────────


async def _generate_json_with_hard_timeout(
    provider: TextGenerationProvider,
    request: TextGenerationRequest,
    *,
    module_id: str,
) -> Any:
    hard_timeout_seconds = request.timeout_seconds + 30
    try:
        return await asyncio.wait_for(provider.generate_json(request), timeout=hard_timeout_seconds)
    except TimeoutError as exc:
        raise ProviderError(
            code=ProviderErrorCode.TIMEOUT,
            message=f"[deepseek] {module_id} exceeded hard timeout ({hard_timeout_seconds}s)",
            provider="deepseek",
            raw_error=f"module={module_id}",
        ) from exc


def _merge_stage_results(module_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    if module_id == "character_extractor":
        return {"characters": [item for result in results for item in _as_list(result.get("characters"))]}
    if module_id == "scene_extractor":
        return {"scenes": [item for result in results for item in _as_list(result.get("scenes"))]}
    if module_id == "prop_extractor":
        return {"props": [item for result in results for item in _as_list(result.get("props"))]}
    if results:
        return results[0]
    return {}


def _chunks(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return [""]
    size = 6000
    return [text[index : index + size] for index in range(0, len(text), size)]


def _clean_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.replace("\r\n", "\n").split("\n") if line.strip())


def _title_from_text(text: str) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first[:80] or "未命名小说"


def _module_model_tier(module_id: str) -> str:
    return "fast" if module_id in ASSET_MODULE_IDS else "default"


def _module_max_tokens(module_id: str) -> int:
    return 4096 if module_id == "genre_detector" else 12000


def _module_timeout(module_id: str) -> int:
    return 60 if module_id == "genre_detector" else 180


def _module_thinking(module_id: str) -> str:
    return "disabled" if module_id in ASSET_MODULE_IDS else settings.deepseek_default_thinking


def _provider_user_id(project_id: str) -> str:
    safe_project_id = re.sub(r"[^A-Za-z0-9_-]", "-", str(project_id)).strip("-_") or "unknown"
    return f"project-{safe_project_id[:56]}"


def _hash_payload(
    style_id: str,
    module_id: str,
    template: StylePackTemplate,
    text: str,
    template_contract: str | None = None,
) -> str:
    raw = json.dumps(
        {
            "style_id": style_id,
            "module_id": module_id,
            "template": template.user_prompt_template,
            "template_contract": template_contract or "",
            "text": text,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── backward-compat re-exports (tests import these private names) ──────

# Existing tests deliberately reach into the module — keep the underscore
# aliases pointing at the extracted implementations so test imports don't
# have to change.
__all__ = [
    "ASSET_MODULE_IDS",
    "DeepSeekAnalysisActivities",
    "create_analysis_activities",
]
