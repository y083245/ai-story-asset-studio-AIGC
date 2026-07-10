"""Business logic for the Image Asset module.

All image generation goes through Provider Adapter.
All file uploads go through StorageService.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.contracts.enums import TaskStatus
from app.db.session import async_session_factory
from app.modules.image_asset.lifecycle import compute_expires_at
from app.modules.image_asset.models import ImageAsset, ImageGenerationTask
from app.modules.image_asset.prompt_builder import (
    build_character_image_prompt,
    build_prop_image_prompt,
    build_scene_empty_prompt,
)
from app.modules.image_asset.schemas import (
    BatchGenerateRequest,
    BatchGenerateResponse,
    GenerateAssetRequest,
    GenerationTaskResponse,
    ImageAssetResponse,
    ImagePromptPreviewResponse,
    QualityCallback,
)
from app.modules.observability.prompt_audit import PromptAuditRecord, write_prompt_audit_record
from app.modules.provider_adapter.base import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from app.modules.storage.service import StorageService
from app.modules.story_bible.models import StoryBible, StoryBibleVersion

logger = logging.getLogger("storyasset.image_asset")

# Asset type -> Storage category mapping
_ASSET_TYPE_CATEGORY: dict[str, str] = {
    "character_bible_sheet": "characters",
    "character_front": "characters",
    "character_turnaround": "characters",
    "character_expression": "characters",
    "scene_empty": "scenes",
    "scene_with_atmosphere": "scenes",
    "prop_product": "props",
    "prop_usage": "props",
}


@dataclass
class _GenerateContext:
    """Internal context for a single asset generation call."""

    project_id: str
    asset_type: str
    related_id: str | None
    reference_asset_ids: list[str]
    extra_constraints: str | None


class ImageAssetService:
    """Service for generating and managing image assets.

    All generation goes through the ImageGenerationProvider interface.
    All uploads go through StorageService.
    """

    def __init__(
        self,
        image_provider: ImageGenerationProvider,
        storage_service: StorageService,
        safety_service: Any = None,
    ) -> None:
        """Initialize the service.

        Args:
            image_provider: Provider adapter for image generation.
            storage_service: Storage service for file uploads.
            safety_service: Deprecated compatibility argument; ignored.
        """
        self._image_provider = image_provider
        self._storage = storage_service
        self._safety = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_asset(
        self,
        request: GenerateAssetRequest,
        db: AsyncSession,
    ) -> ImageAssetResponse:
        """Generate a single image asset.

        Flow:
        1. Load related entity data from database
        2. Build prompt using prompt_builder
        3. Call image provider
        4. Upload result to storage
        5. Create ImageAsset + ImageGenerationTask records
        6. Return response
        """
        ctx = _GenerateContext(
            project_id=str(request.project_id),
            asset_type=request.asset_type,
            related_id=request.related_id,
            reference_asset_ids=request.reference_asset_ids,
            extra_constraints=request.extra_constraints,
        )

        # 1. Build prompt
        prompt, negative_prompt = await self._build_prompt(ctx, db)
        width, height = _dimensions_for_asset(ctx.asset_type)
        reference_images = await self._load_reference_images(ctx.reference_asset_ids)

        # 2. Build provider request and generate
        timeout_seconds = _timeout_for_asset(ctx.asset_type)
        provider_request = ImageGenerationRequest(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            reference_images=reference_images,
            timeout_seconds=timeout_seconds,
        )

        # Create task record (pending)
        task = await self._create_task(ctx, prompt, negative_prompt, width, height, timeout_seconds, db)
        task.status = TaskStatus.RUNNING

        # 3. Call provider
        try:
            response = await self._image_provider.generate(provider_request)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            await db.flush()
            raise

        # 4. Upload image to storage
        asset = await self._upload_and_create_asset(
            ctx=ctx,
            db=db,
            task=task,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model_name=response.model or "unknown",
            provider_task_id=response.provider_task_id,
            image_bytes=response.images[0] if response.images else b"",
            width=width,
            height=height,
        )
        await self._append_reference_to_owner(ctx, asset.storage_path, db)
        with contextlib.suppress(Exception):
            write_prompt_audit_record(
                PromptAuditRecord(
                    project_id=ctx.project_id,
                    entity_type="image_asset",
                    entity_id=str(asset.id),
                    asset_type=ctx.asset_type,
                    stage="final_generation",
                    source_prompt=prompt,
                    final_prompt=prompt,
                    negative_prompt=negative_prompt,
                    provider=_provider_id(self._image_provider),
                    model=response.model or _provider_model_name(self._image_provider),
                    metadata={
                        "related_id": ctx.related_id or "",
                        "generation_task_id": str(task.id),
                        "reference_asset_ids": ctx.reference_asset_ids,
                        "width": width,
                        "height": height,
                    },
                )
            )

        # 5. Update task
        task.status = TaskStatus.SUCCESS
        task.response_json = {
            "image_urls": response.image_urls,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "provider_task_id": response.provider_task_id,
        }
        asset.generation_task_id = task.id
        await db.flush()

        return ImageAssetResponse.model_validate(asset)

    async def build_prompt_preview(
        self,
        request: GenerateAssetRequest,
        db: AsyncSession,
    ) -> ImagePromptPreviewResponse:
        """Build the final prompt without calling the image provider or writing assets."""
        ctx = _GenerateContext(
            project_id=str(request.project_id),
            asset_type=request.asset_type,
            related_id=request.related_id,
            reference_asset_ids=request.reference_asset_ids,
            extra_constraints=request.extra_constraints,
        )
        prompt, negative_prompt = await self._build_prompt(ctx, db)
        return ImagePromptPreviewResponse(prompt=prompt, negative_prompt=negative_prompt)

    async def generate_batch(
        self,
        request: BatchGenerateRequest,
        db: AsyncSession,
    ) -> BatchGenerateResponse:
        """Generate multiple image assets for a project.

        Each asset is generated independently. Partial failures are
        tolerated — the response reports succeeded vs failed counts.
        """
        results: list[ImageAssetResponse] = []
        succeeded = 0
        failed = 0

        for req in request.requests:
            try:
                result = await self.generate_asset(req, db)
                results.append(result)
                succeeded += 1
            except Exception as exc:
                logger.warning(
                    "Batch generation failed for asset_type=%s related_id=%s: %s",
                    req.asset_type,
                    req.related_id,
                    exc,
                )
                failed += 1

        return BatchGenerateResponse(
            project_id=request.project_id,
            results=results,
            total=len(request.requests),
            succeeded=succeeded,
            failed=failed,
        )

    async def create_generation_job(
        self,
        request: GenerateAssetRequest,
        db: AsyncSession,
    ) -> ImageGenerationTask:
        """Create a generation task record (status=pending) without calling the provider.

        The actual generation runs asynchronously via execute_generation_job().
        """
        ctx = _GenerateContext(
            project_id=str(request.project_id),
            asset_type=request.asset_type,
            related_id=request.related_id,
            reference_asset_ids=request.reference_asset_ids,
            extra_constraints=request.extra_constraints,
        )

        prompt, negative_prompt = await self._build_prompt(ctx, db)
        width, height = _dimensions_for_asset(ctx.asset_type)
        timeout_seconds = _timeout_for_asset(ctx.asset_type)

        task = await self._create_task(ctx, prompt, negative_prompt, width, height, timeout_seconds, db)
        return task

    async def get_asset(self, asset_id: uuid.UUID, db: AsyncSession) -> ImageAssetResponse:
        """Get asset details by ID."""
        asset = await self._get_asset_or_404(asset_id, db)
        return ImageAssetResponse.model_validate(asset)

    async def get_task(self, task_id: uuid.UUID, db: AsyncSession) -> GenerationTaskResponse:
        """Get generation task status by ID."""
        task = await self._get_task_or_404(task_id, db)
        response = GenerationTaskResponse.model_validate(task)
        # Attach asset_id when task succeeded and an asset was created
        if task.status == TaskStatus.SUCCESS:
            asset_result = await db.execute(
                select(ImageAsset).where(ImageAsset.generation_task_id == task_id)
            )
            asset = asset_result.scalar_one_or_none()
            if asset is not None:
                response.asset_id = asset.id
                response.storage_path = asset.storage_path
        return response

    async def retry_task(
        self,
        task_id: uuid.UUID,
        db: AsyncSession,
    ) -> ImageAssetResponse:
        """Retry a failed task (max 3 retries, add negative prompt on retry).

        Only tasks with status=failed are eligible for retry.
        Retry count is tracked on the task record.
        """
        task = await self._get_task_or_404(task_id, db)

        if task.status != TaskStatus.FAILED:
            raise ValueError(f"Task {task_id} is not in failed status (current: {task.status})")

        if task.retry_count >= task.max_retries:
            raise ValueError(f"Task {task_id} has reached max retries ({task.max_retries})")

        # Build retry request from task data
        request_json: dict[str, object] = task.request_json or {}
        prompt: str = str(request_json.get("prompt", ""))
        negative_prompt: str = str(request_json.get("negative_prompt", ""))

        # Add more negative prompts on retry
        enhanced_negative = _enhance_negative_for_retry(negative_prompt, task.retry_count + 1)

        provider_request = ImageGenerationRequest(
            prompt=_simplify_prompt_for_retry(prompt, task.retry_count + 1),
            negative_prompt=enhanced_negative,
            width=cast(int, request_json.get("width", 1080)),
            height=cast(int, request_json.get("height", 1920)),
            timeout_seconds=120,
        )

        # Update task
        task.status = TaskStatus.RETRYING
        task.retry_count += 1
        await db.flush()

        # Call provider
        try:
            response = await self._image_provider.generate(provider_request)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            await db.flush()
            raise

        # Create new asset
        ctx = _GenerateContext(
            project_id=str(task.project_id),
            asset_type=task.asset_type,
            related_id=task.related_id,
            reference_asset_ids=[],
            extra_constraints=None,
        )

        asset = await self._upload_and_create_asset(
            ctx=ctx,
            db=db,
            task=task,
            prompt=provider_request.prompt,
            negative_prompt=provider_request.negative_prompt,
            model_name=response.model or task.model_name,
            provider_task_id=response.provider_task_id,
            image_bytes=response.images[0] if response.images else b"",
            width=provider_request.width,
            height=provider_request.height,
        )

        task.status = TaskStatus.SUCCESS
        task.response_json = {
            "image_urls": response.image_urls,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "provider_task_id": response.provider_task_id,
        }
        asset.generation_task_id = task.id
        await db.flush()

        return ImageAssetResponse.model_validate(asset)

    async def handle_quality_callback(
        self,
        callback: QualityCallback,
        db: AsyncSession,
    ) -> None:
        """Receive quality results from M13 and mark tasks needing retry.

        Does NOT perform quality assessment itself — only records the
        M13 result on the generation task and optionally triggers retry.
        """
        task = await self._get_task_or_404(callback.generation_task_id, db)

        task.quality_status = callback.quality_status
        task.quality_report_id = callback.quality_report_id

        if callback.quality_status == "needs_retry" and task.status == TaskStatus.SUCCESS:
            task.status = TaskStatus.FAILED
            if callback.retry_prompt_patch:
                # Store the patch suggestion for retry
                request_json = dict(task.request_json)
                request_json["quality_retry_patch"] = callback.retry_prompt_patch
                task.request_json = request_json

        await db.flush()

    async def list_project_assets(
        self,
        project_id: uuid.UUID,
        asset_type: str | None,
        db: AsyncSession,
    ) -> list[ImageAssetResponse]:
        """List all image assets for a project, optionally filtered by type."""
        stmt = select(ImageAsset).where(ImageAsset.project_id == project_id)

        if asset_type:
            stmt = stmt.where(ImageAsset.asset_type == asset_type)

        stmt = stmt.order_by(ImageAsset.created_at.desc())
        result = await db.execute(stmt)
        assets = result.scalars().all()

        return [ImageAssetResponse.model_validate(a) for a in assets]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_prompt(self, ctx: _GenerateContext, db: AsyncSession) -> tuple[str, str]:
        """Build prompt and negative prompt for the given asset type."""
        asset_type = ctx.asset_type

        if asset_type.startswith("character_"):
            return await self._build_character_prompt(ctx, db)
        elif asset_type.startswith("scene_"):
            return await self._build_scene_prompt(ctx, db)
        elif asset_type.startswith("prop_"):
            return await self._build_prop_prompt(ctx, db)
        else:
            raise ValueError(f"Unknown asset_type: {asset_type}")

    async def _build_character_prompt(self, ctx: _GenerateContext, db: AsyncSession) -> tuple[str, str]:
        """Build character image prompt from Character ORM."""
        from app.modules.character_library.models import Character

        if not ctx.related_id:
            raise ValueError("related_id is required for character asset types")
        project_id = uuid.UUID(ctx.project_id)

        result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.character_id == ctx.related_id,
            )
        )
        character = result.scalar_one_or_none()
        if character is None:
            raise ValueError(f"Character {ctx.related_id} not found in project {ctx.project_id}")

        image_type = ctx.asset_type.replace("character_", "")
        # Map to prompt builder image_type
        image_type_map = {
            "bible_sheet": "character_bible_sheet",
            "front": "character_front",
            "turnaround": "character_turnaround",
            "expression": "character_expression",
        }
        mapped_type = image_type_map.get(image_type, image_type)
        story_bible = await self._load_story_bible_context(project_id, db) if settings.prompt_engine_mode == "staged" else None

        return build_character_image_prompt(
            character=character,
            story_bible=story_bible,
            image_type=mapped_type,
            extra_constraints=ctx.extra_constraints,
        )

    async def _build_scene_prompt(self, ctx: _GenerateContext, db: AsyncSession) -> tuple[str, str]:
        """Build scene empty prompt from Scene ORM."""
        from app.modules.scene_library.models import Scene

        if not ctx.related_id:
            raise ValueError("related_id is required for scene_empty asset type")
        project_id = uuid.UUID(ctx.project_id)

        result = await db.execute(
            select(Scene).where(
                Scene.project_id == project_id,
                Scene.scene_id == ctx.related_id,
            )
        )
        scene = result.scalar_one_or_none()
        if scene is None:
            raise ValueError(f"Scene {ctx.related_id} not found in project {ctx.project_id}")
        story_bible = await self._load_story_bible_context(project_id, db) if settings.prompt_engine_mode == "staged" else None

        image_type = "scene_with_atmosphere" if ctx.asset_type == "scene_with_atmosphere" else "scene_empty"
        return build_scene_empty_prompt(
            scene=scene,
            story_bible=story_bible,
            image_type=image_type,
            extra_constraints=ctx.extra_constraints,
        )

    async def _build_prop_prompt(self, ctx: _GenerateContext, db: AsyncSession) -> tuple[str, str]:
        """Build prop image prompt from Prop ORM."""
        from app.modules.character_library.models import Character
        from app.modules.prop_library.models import Prop

        if not ctx.related_id:
            raise ValueError("related_id is required for prop asset types")
        project_id = uuid.UUID(ctx.project_id)

        result = await db.execute(
            select(Prop).where(
                Prop.project_id == project_id,
                Prop.prop_id == ctx.related_id,
            )
        )
        prop = result.scalar_one_or_none()
        if prop is None:
            raise ValueError(f"Prop {ctx.related_id} not found in project {ctx.project_id}")

        # Load owner character if specified
        character = None
        owner_id = getattr(prop, "owner_character_id", None)
        if owner_id:
            char_result = await db.execute(
                select(Character).where(
                    Character.project_id == project_id,
                    Character.character_id == owner_id,
                )
            )
            character = char_result.scalar_one_or_none()

        image_type = ctx.asset_type.replace("prop_", "")
        image_type_map = {
            "product": "prop_product",
            "usage": "prop_usage",
        }
        mapped_type = image_type_map.get(image_type, image_type)
        story_bible = await self._load_story_bible_context(project_id, db) if settings.prompt_engine_mode == "staged" else None

        return build_prop_image_prompt(
            prop=prop,
            story_bible=story_bible,
            character=character,
            image_type=mapped_type,
            extra_constraints=ctx.extra_constraints,
        )

    async def _load_story_bible_context(self, project_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
        """Return the newest story bible snapshot available for prompt building."""
        version_result = await db.execute(
            select(StoryBibleVersion)
            .where(StoryBibleVersion.project_id == project_id)
            .order_by(StoryBibleVersion.version.desc())
        )
        version = version_result.scalars().first()
        if version is not None and isinstance(version.snapshot, dict):
            return dict(version.snapshot)

        bible_result = await db.execute(select(StoryBible).where(StoryBible.project_id == project_id))
        bible = bible_result.scalar_one_or_none()
        if bible is None:
            return {}
        return {
            "project_id": str(bible.project_id),
            "version": bible.version,
            "title": bible.title,
            "genre": bible.genre,
            "visual_style": bible.visual_style,
            "aspect_ratio": bible.aspect_ratio,
            "story_summary": bible.story_summary,
            "main_conflict": bible.main_conflict,
            "emotional_tone": bible.emotional_tone,
            "world_setting": bible.world_setting,
            "time_period": bible.time_period,
            "color_palette": list(bible.color_palette or []),
            "composition_language": list(bible.composition_language or []),
            "characters": list(bible.characters or []),
            "scenes": list(bible.scenes or []),
            "props": list(bible.props or []),
            "negative_prompt_rules": list(bible.negative_prompt_rules or []),
        }

    async def _load_reference_images(self, reference_asset_ids: list[str]) -> list[bytes]:
        """Load reference image bytes from storage for provider adapters that support them."""
        images: list[bytes] = []
        for asset_id in reference_asset_ids:
            try:
                images.append(await self._storage.download(asset_id))
            except Exception as exc:  # pragma: no cover - defensive logging around storage flakiness
                logger.warning("Could not load reference image asset_id=%s: %s", asset_id, exc)
        return images

    async def _append_reference_to_owner(self, ctx: _GenerateContext, storage_path: str, db: AsyncSession) -> None:
        """Backfill generated character, scene, and prop asset paths to their owner rows."""
        if not ctx.related_id or not storage_path:
            return

        owner: Any | None = None
        project_id = uuid.UUID(ctx.project_id)
        if ctx.asset_type.startswith("character_"):
            from app.modules.character_library.models import Character

            result = await db.execute(
                select(Character).where(
                    Character.project_id == project_id,
                    Character.character_id == ctx.related_id,
                )
            )
            owner = result.scalar_one_or_none()
        elif ctx.asset_type.startswith("scene_"):
            from app.modules.scene_library.models import Scene

            result = await db.execute(
                select(Scene).where(
                    Scene.project_id == project_id,
                    Scene.scene_id == ctx.related_id,
                )
            )
            owner = result.scalar_one_or_none()
        elif ctx.asset_type.startswith("prop_"):
            from app.modules.prop_library.models import Prop

            result = await db.execute(
                select(Prop).where(
                    Prop.project_id == project_id,
                    Prop.prop_id == ctx.related_id,
                )
            )
            owner = result.scalar_one_or_none()

        if owner is None:
            return
        reference_assets = list(owner.reference_assets or [])
        next_reference_assets = _replace_reference_asset_by_type(
            reference_assets,
            storage_path=storage_path,
            asset_type=ctx.asset_type,
        )
        if next_reference_assets != reference_assets:
            owner.reference_assets = next_reference_assets
            await db.flush()

    async def _build_storage_category(self, asset_type: str) -> str:
        """Map asset_type to StorageService category."""
        if asset_type not in _ASSET_TYPE_CATEGORY:
            raise ValueError(f"Unsupported asset_type: {asset_type}")
        return _ASSET_TYPE_CATEGORY[asset_type]

    async def _create_task(
        self,
        ctx: _GenerateContext,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        timeout_seconds: int,
        db: AsyncSession,
    ) -> ImageGenerationTask:
        """Create an ImageGenerationTask record in pending status."""
        task = ImageGenerationTask(
            project_id=uuid.UUID(ctx.project_id),
            asset_type=ctx.asset_type,
            related_id=ctx.related_id,
            provider=_provider_id(self._image_provider),
            model_name=_provider_model_name(self._image_provider),
            request_json={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "timeout_seconds": timeout_seconds,
                "reference_asset_ids": ctx.reference_asset_ids,
            },
            status=TaskStatus.PENDING,
            retry_count=0,
            max_retries=3,
        )
        db.add(task)
        await db.flush()
        return task

    async def _update_task_success(
        self,
        task: ImageGenerationTask,
        response: Any,
    ) -> None:
        """Mark generation task as successful."""
        task.status = TaskStatus.SUCCESS
        task.response_json = {
            "image_urls": response.image_urls,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "provider_task_id": response.provider_task_id,
        }

    async def _upload_and_create_asset(
        self,
        ctx: _GenerateContext,
        db: AsyncSession,
        task: ImageGenerationTask,
        prompt: str,
        negative_prompt: str,
        model_name: str,
        provider_task_id: str,
        image_bytes: bytes,
        width: int,
        height: int,
    ) -> ImageAsset:
        """Upload image bytes to storage and create ImageAsset record."""
        extension, content_type = _detect_image_format(image_bytes)
        file_name = f"{ctx.asset_type}.{extension}"
        category = await self._build_storage_category(ctx.asset_type)

        # Build path kwargs for storage
        path_kwargs: dict[str, str] = {}
        if category == "characters" and ctx.related_id:
            path_kwargs["character_id"] = ctx.related_id
            path_kwargs["asset_name"] = ctx.asset_type.replace("character_", "")
        elif category == "scenes" and ctx.related_id:
            path_kwargs["scene_id"] = ctx.related_id
            path_kwargs["asset_name"] = ctx.asset_type.replace("scene_", "")
        elif category == "props" and ctx.related_id:
            path_kwargs["prop_id"] = ctx.related_id
            path_kwargs["asset_name"] = ctx.asset_type.replace("prop_", "")

        # Upload
        upload_result = await self._storage.upload(
            file_bytes=image_bytes,
            file_name=file_name,
            content_type=content_type,
            project_id=ctx.project_id,
            asset_type=category,
            **path_kwargs,
        )

        # Create asset record
        created_at = datetime.now(UTC)
        asset = ImageAsset(
            project_id=uuid.UUID(ctx.project_id),
            asset_type=ctx.asset_type,
            related_id=ctx.related_id,
            asset_url=upload_result.url,
            thumbnail_url=None,
            storage_path=upload_result.asset_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model_name=model_name,
            provider_task_id=provider_task_id,
            generation_task_id=task.id,
            width=width,
            height=height,
            reference_asset_ids=ctx.reference_asset_ids,
            status="completed",
            created_at=created_at,
            updated_at=created_at,
            expires_at=compute_expires_at(created_at),
        )
        db.add(asset)
        await db.flush()
        return asset

    @staticmethod
    async def _get_asset_or_404(asset_id: uuid.UUID, db: AsyncSession) -> ImageAsset:
        """Get ImageAsset by ID or raise ValueError."""
        result = await db.execute(select(ImageAsset).where(ImageAsset.id == asset_id))
        asset = result.scalar_one_or_none()
        if asset is None:
            raise ValueError(f"ImageAsset {asset_id} not found")
        return asset

    @staticmethod
    async def _get_task_or_404(task_id: uuid.UUID, db: AsyncSession) -> ImageGenerationTask:
        """Get ImageGenerationTask by ID or raise ValueError."""
        result = await db.execute(select(ImageGenerationTask).where(ImageGenerationTask.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise ValueError(f"ImageGenerationTask {task_id} not found")
        return task


def _replace_reference_asset_by_type(
    reference_assets: list[str],
    *,
    storage_path: str,
    asset_type: str,
) -> list[str]:
    stem = _asset_stem(asset_type)
    if stem is None:
        return reference_assets if storage_path in reference_assets else [*reference_assets, storage_path]

    next_assets: list[str] = []
    inserted = False
    for asset_path in reference_assets:
        if _storage_path_matches_stem(asset_path, stem):
            if not inserted:
                next_assets.append(storage_path)
                inserted = True
            continue
        if asset_path != storage_path:
            next_assets.append(asset_path)

    if not inserted:
        next_assets.append(storage_path)
    return next_assets


def _asset_stem(asset_type: str) -> str | None:
    for prefix in ("character_", "scene_", "prop_"):
        if asset_type.startswith(prefix):
            return asset_type.removeprefix(prefix)
    return None


def _storage_path_matches_stem(storage_path: str, stem: str) -> bool:
    suffix = storage_path.rsplit("/", maxsplit=1)[-1].lower()
    return suffix in {f"{stem}.png", f"{stem}.jpg", f"{stem}.jpeg", f"{stem}.webp"}


async def execute_generation_job(task_id: str) -> None:
    """Run a generation task asynchronously with its own database session.

    Creates independent provider and storage instances — does NOT reuse
    any request-scoped resources.  All provider/storage errors are caught
    and persisted to the task record so the frontend can surface them.
    """
    from app.modules.provider_adapter.fake import FakeSeedreamProvider
    from app.modules.provider_adapter.registry import ProviderRegistry
    from app.modules.storage.service import StorageService

    task_uuid = uuid.UUID(task_id)

    # Build our own service instances (no dependency on request scope)
    registry = ProviderRegistry()
    try:
        image_provider = registry.get_image_generator()
    except Exception:
        image_provider = FakeSeedreamProvider()
    if image_provider is None:
        image_provider = FakeSeedreamProvider()

    storage_service = StorageService.create()
    service = ImageAssetService(
        image_provider=image_provider,
        storage_service=storage_service,
    )

    async with async_session_factory() as db:
        try:
            # Load task
            result = await db.execute(
                select(ImageGenerationTask).where(ImageGenerationTask.id == task_uuid)
            )
            task = result.scalar_one_or_none()
            if task is None:
                logger.error("execute_generation_job: task %s not found", task_id)
                return

            task.status = TaskStatus.RUNNING
            await db.flush()
            await db.commit()

            # Reconstruct request from task payload
            request_json: dict[str, object] = task.request_json or {}
            prompt = str(request_json.get("prompt", ""))
            negative_prompt = str(request_json.get("negative_prompt", ""))
            width = int(request_json.get("width", 1080))  # type: ignore[arg-type]
            height = int(request_json.get("height", 1920))  # type: ignore[arg-type]
            timeout_seconds = int(request_json.get("timeout_seconds", 120))  # type: ignore[arg-type]
            reference_asset_ids: list[str] = [
                str(item) for item in request_json.get("reference_asset_ids", []) or []
            ]

            # Load reference images
            reference_images: list[bytes] = []
            for asset_id_str in reference_asset_ids:
                try:
                    reference_images.append(await storage_service.download(asset_id_str))
                except Exception as exc:
                    logger.warning(
                        "execute_generation_job: could not load reference image asset_id=%s: %s",
                        asset_id_str,
                        exc,
                    )

            # Call provider
            provider_request = ImageGenerationRequest(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                reference_images=reference_images,
                timeout_seconds=timeout_seconds,
            )
            response = await image_provider.generate(provider_request)

            # Upload image to storage
            ctx = _GenerateContext(
                project_id=str(task.project_id),
                asset_type=task.asset_type,
                related_id=task.related_id,
                reference_asset_ids=reference_asset_ids,
                extra_constraints=None,
            )

            extension, content_type = _detect_image_format(
                response.images[0] if response.images else b""
            )
            file_name = f"{task.asset_type}.{extension}"
            category = await service._build_storage_category(task.asset_type)

            path_kwargs: dict[str, str] = {}
            if category == "characters" and task.related_id:
                path_kwargs["character_id"] = task.related_id
                path_kwargs["asset_name"] = task.asset_type.replace("character_", "")
            elif category == "scenes" and task.related_id:
                path_kwargs["scene_id"] = task.related_id
                path_kwargs["asset_name"] = task.asset_type.replace("scene_", "")
            elif category == "props" and task.related_id:
                path_kwargs["prop_id"] = task.related_id
                path_kwargs["asset_name"] = task.asset_type.replace("prop_", "")

            upload_result = await storage_service.upload(
                file_bytes=response.images[0] if response.images else b"",
                file_name=file_name,
                content_type=content_type,
                project_id=str(task.project_id),
                asset_type=category,
                **path_kwargs,
            )

            # Create ImageAsset
            created_at = datetime.now(UTC)
            asset = ImageAsset(
                project_id=task.project_id,
                asset_type=task.asset_type,
                related_id=task.related_id,
                asset_url=upload_result.url,
                thumbnail_url=None,
                storage_path=upload_result.asset_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                model_name=response.model or task.model_name,
                provider_task_id=response.provider_task_id,
                generation_task_id=task.id,
                width=width,
                height=height,
                reference_asset_ids=reference_asset_ids,
                status="completed",
                created_at=created_at,
                updated_at=created_at,
                expires_at=compute_expires_at(created_at),
            )
            db.add(asset)
            await db.flush()

            # Backfill reference asset on owner entity
            await service._append_reference_to_owner(ctx, asset.storage_path, db)

            # Mark task success
            task.status = TaskStatus.SUCCESS
            task.response_json = {
                "image_urls": response.image_urls,
                "model": response.model,
                "latency_ms": response.latency_ms,
                "provider_task_id": response.provider_task_id,
                "asset_id": str(asset.id),
            }

            with contextlib.suppress(Exception):
                write_prompt_audit_record(
                    PromptAuditRecord(
                        project_id=str(task.project_id),
                        entity_type="image_asset",
                        entity_id=str(asset.id),
                        asset_type=task.asset_type,
                        stage="final_generation",
                        source_prompt=prompt,
                        final_prompt=prompt,
                        negative_prompt=negative_prompt,
                        provider=_provider_id(image_provider),
                        model=response.model or _provider_model_name(image_provider),
                        metadata={
                            "related_id": task.related_id or "",
                            "generation_task_id": str(task.id),
                            "reference_asset_ids": reference_asset_ids,
                            "width": width,
                            "height": height,
                        },
                    )
                )

            await db.commit()
            logger.info("execute_generation_job: task %s completed successfully", task_id)

        except Exception as exc:
            await db.rollback()
            # Reload task within the rolled-back session to update status
            try:
                result = await db.execute(
                    select(ImageGenerationTask).where(ImageGenerationTask.id == task_uuid)
                )
                failed_task = result.scalar_one_or_none()
                if failed_task is not None:
                    failed_task.status = TaskStatus.FAILED
                    failed_task.error_message = str(exc)
                    await db.commit()
            except Exception as inner_exc:
                logger.error(
                    "execute_generation_job: could not persist failure for task %s: %s",
                    task_id,
                    inner_exc,
                )
            logger.error("execute_generation_job: task %s failed: %s", task_id, exc)


def _detect_image_format(image_bytes: bytes) -> tuple[str, str]:
    """Return storage extension and MIME type from common image signatures."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "webp", "image/webp"
    return "png", "image/png"


def _provider_id(provider: ImageGenerationProvider) -> str:
    configured = getattr(provider, "provider_id", "")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    class_name = provider.__class__.__name__.lower()
    if "fake" in class_name:
        return "fake-seedream"
    if "flux" in class_name:
        return "replicate"
    if "dalle" in class_name:
        return "openai"
    return "doubao_seedream"


def _provider_model_name(provider: ImageGenerationProvider) -> str:
    configured = getattr(provider, "model_name", "")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return provider.__class__.__name__


# =============================================================================
# Retry helpers
# =============================================================================


def _enhance_negative_for_retry(negative_prompt: str, retry_attempt: int) -> str:
    """Add more negative prompts based on retry attempt number."""
    extra_negatives = {
        1: "低质量，模糊",
        2: "低质量，模糊，变形，构图混乱",
        3: "低质量，模糊，变形，构图混乱，颜色失真，噪点",
    }
    extra = extra_negatives.get(retry_attempt, "低质量")
    if negative_prompt:
        return f"{negative_prompt}，{extra}"
    return extra


def _dimensions_for_asset(asset_type: str) -> tuple[int, int]:
    """Return generation dimensions that fit the visual layout of each asset."""
    if asset_type == "character_bible_sheet":
        return _parse_dimensions(settings.canonical_bible_sheet_dimensions, fallback=(1440, 2560))
    if asset_type == "character_turnaround":
        return 2560, 1440
    if asset_type.startswith("scene_"):
        return 2560, 1440
    if asset_type.startswith("prop_"):
        return 1920, 1920
    return 1440, 2560


def _timeout_for_asset(asset_type: str) -> int:
    if asset_type == "character_bible_sheet":
        return settings.canonical_bible_sheet_timeout_seconds
    return 120


def _parse_dimensions(value: str, *, fallback: tuple[int, int]) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", maxsplit=1)
        width = int(width_text.strip())
        height = int(height_text.strip())
    except (AttributeError, TypeError, ValueError):
        return fallback
    if width <= 0 or height <= 0:
        return fallback
    return width, height


def _simplify_prompt_for_retry(prompt: str, retry_attempt: int) -> str:
    """Simplify the prompt composition on retry to reduce complexity.

    On later retries, remove some detail to give the model more freedom.
    """
    if retry_attempt <= 1:
        return prompt

    # On retry 2+, simplify by removing some constraints
    if retry_attempt >= 3:
        # Keep only the core description
        parts = prompt.split("。")
        if len(parts) > 2:
            return "。".join(parts[:2]) + "。"
    return prompt
