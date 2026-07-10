"""Service for one-click reference asset generation across library modules."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.asset_workbench.schemas import (
    GenerateAssetWorkbenchRequest,
    GenerateAssetWorkbenchResponse,
    GeneratedAssetItem,
    PreviewAssetWorkbenchPromptsRequest,
    PreviewAssetWorkbenchPromptsResponse,
    PromptPreviewResult,
)
from app.modules.character_library.models import Character
from app.modules.image_asset.schemas import GenerateAssetRequest
from app.modules.image_asset.service import ImageAssetService
from app.modules.prop_library.models import Prop
from app.modules.scene_library.models import Scene

logger = logging.getLogger("storyasset.asset_workbench")


class AssetWorkbenchService:
    """Generate characters, scenes, and props through the existing image service."""

    def __init__(self, image_asset_service: ImageAssetService) -> None:
        self._image_asset_service = image_asset_service

    async def generate_reference_assets(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        request: GenerateAssetWorkbenchRequest,
    ) -> GenerateAssetWorkbenchResponse:
        """Generate selected reference assets with partial-failure reporting."""
        results: list[GeneratedAssetItem] = []

        if "characters" in request.targets:
            for character in await self._load_characters(session, project_id):
                front_path = _existing_asset_path(character.reference_assets, "character_front")
                front_result = await self._generate_one(
                    session=session,
                    project_id=project_id,
                    entity_type="character",
                    entity_id=character.character_id,
                    asset_type="character_front",
                    owner=character,
                    only_missing=request.only_missing,
                )
                results.append(front_result)
                if front_result.storage_path:
                    front_path = front_result.storage_path
                elif front_result.status == "failed" and not front_path:
                    results.append(
                        GeneratedAssetItem(
                            entity_type="character",
                            entity_id=character.character_id,
                            asset_type="character_turnaround",
                            status="failed",
                            error="Cannot generate character_turnaround without a front reference image",
                        )
                    )
                    continue

                turnaround_result = await self._generate_one(
                    session=session,
                    project_id=project_id,
                    entity_type="character",
                    entity_id=character.character_id,
                    asset_type="character_turnaround",
                    owner=character,
                    reference_asset_ids=[front_path] if front_path else [],
                    only_missing=request.only_missing,
                )
                results.append(turnaround_result)

        if "scenes" in request.targets:
            for scene in await self._load_scenes(session, project_id):
                results.append(
                    await self._generate_one(
                        session=session,
                        project_id=project_id,
                        entity_type="scene",
                        entity_id=scene.scene_id,
                        asset_type="scene_empty",
                        owner=scene,
                        only_missing=request.only_missing,
                    )
                )

        if "props" in request.targets:
            for prop in await self._load_props(session, project_id):
                results.append(
                    await self._generate_one(
                        session=session,
                        project_id=project_id,
                        entity_type="prop",
                        entity_id=prop.prop_id,
                        asset_type="prop_product",
                        owner=prop,
                        only_missing=request.only_missing,
                    )
                )

        await session.flush()
        return GenerateAssetWorkbenchResponse(
            project_id=project_id,
            total=len(results),
            succeeded=sum(1 for item in results if item.status == "generated"),
            skipped=sum(1 for item in results if item.status == "skipped"),
            failed=sum(1 for item in results if item.status == "failed"),
            results=results,
        )

    async def preview_prompts(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        request: PreviewAssetWorkbenchPromptsRequest,
    ) -> PreviewAssetWorkbenchPromptsResponse:
        """Build final prompts for workbench display without generating images."""
        results: list[PromptPreviewResult] = []
        for item in request.items:
            preview = await self._image_asset_service.build_prompt_preview(
                GenerateAssetRequest(
                    project_id=project_id,
                    asset_type=item.asset_type,
                    related_id=item.entity_id,
                    reference_asset_ids=item.reference_asset_ids,
                    extra_constraints=item.extra_constraints,
                ),
                session,
            )
            results.append(
                PromptPreviewResult(
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    asset_type=item.asset_type,
                    prompt=preview.prompt,
                    negative_prompt=preview.negative_prompt,
                )
            )
        return PreviewAssetWorkbenchPromptsResponse(items=results)

    async def _generate_one(
        self,
        *,
        session: AsyncSession,
        project_id: uuid.UUID,
        entity_type: str,
        entity_id: str,
        asset_type: str,
        owner: Any,
        extra_constraints: str | None = None,
        reference_asset_ids: list[str] | None = None,
        only_missing: bool = False,
    ) -> GeneratedAssetItem:
        existing_path = _existing_asset_path(owner.reference_assets, asset_type)
        if only_missing and existing_path:
            return GeneratedAssetItem(
                entity_type=entity_type,
                entity_id=entity_id,
                asset_type=asset_type,
                status="skipped",
                storage_path=existing_path,
            )

        try:
            generated = await self._image_asset_service.generate_asset(
                GenerateAssetRequest(
                    project_id=project_id,
                    asset_type=asset_type,
                    related_id=entity_id,
                    reference_asset_ids=reference_asset_ids or [],
                    extra_constraints=extra_constraints,
                ),
                session,
            )
        except Exception as exc:
            logger.warning(
                "Asset workbench generation failed entity_type=%s entity_id=%s asset_type=%s: %s",
                entity_type,
                entity_id,
                asset_type,
                exc,
            )
            return GeneratedAssetItem(
                entity_type=entity_type,
                entity_id=entity_id,
                asset_type=asset_type,
                status="failed",
                error=str(exc),
            )

        _append_reference_asset(owner, generated.storage_path)
        return GeneratedAssetItem(
            entity_type=entity_type,
            entity_id=entity_id,
            asset_type=asset_type,
            status="generated",
            storage_path=generated.storage_path,
        )

    @staticmethod
    async def _load_characters(session: AsyncSession, project_id: uuid.UUID) -> list[Character]:
        result = await session.execute(
            select(Character).where(Character.project_id == project_id).order_by(Character.sort_order, Character.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _load_scenes(session: AsyncSession, project_id: uuid.UUID) -> list[Scene]:
        result = await session.execute(
            select(Scene).where(Scene.project_id == project_id).order_by(Scene.sort_order, Scene.scene_name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _load_props(session: AsyncSession, project_id: uuid.UUID) -> list[Prop]:
        result = await session.execute(select(Prop).where(Prop.project_id == project_id).order_by(Prop.name))
        return list(result.scalars().all())


def _append_reference_asset(owner: Any, storage_path: str | None) -> None:
    if not storage_path:
        return
    current = list(owner.reference_assets or [])
    if storage_path not in current:
        current.append(storage_path)
    owner.reference_assets = current


def _existing_asset_path(reference_assets: list[str] | None, asset_type: str) -> str | None:
    if not reference_assets:
        return None
    expected = {
        "character_front": ("character_front", "front"),
        "character_turnaround": ("character_turnaround", "turnaround"),
        "scene_empty": ("scene_empty", "empty"),
        "prop_product": ("prop_product", "product"),
    }.get(asset_type, (asset_type,))
    suffixes = tuple(f"/{stem}.{extension}" for stem in expected for extension in ("png", "jpg", "jpeg", "webp"))
    for asset_path in reversed(reference_assets):
        if asset_path.lower().endswith(suffixes):
            return asset_path
    return None
